"""Japan buying-agent & package-forwarding site (代購／集運).

Run:  python app.py   (first run creates data/site.db and an admin account
from ADMIN_EMAIL / ADMIN_PASSWORD, default admin@example.com / admin1234).
"""
import functools
import os
import secrets
from datetime import datetime, timedelta

import markdown as md
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

import db as dbm
from db import get_db, get_setting, set_setting
from pricing import load_rules, shipping_fee
from seed import seed

BASE = os.path.dirname(os.path.abspath(__file__))

PURCHASE_FLOW = ["待採購", "已採購", "已入庫", "已取消"]
SHIPMENT_FLOW = ["待秤重", "待付款", "已付款", "已出貨", "已送達", "已取消"]
CURRENCIES = ("TWD", "JPY")
# Help-centre categories keep the order they were first created in.
DOC_ORDER = ("(SELECT MIN(id) FROM articles a2 WHERE a2.category=articles.category AND a2.is_faq=0), "
             "sort, id")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=os.environ.get("DATABASE", os.path.join(BASE, "data", "site.db")),
        SITE_NAME=os.environ.get("SITE_NAME", "日貨通 JPGO"),
        SITE_TAGLINE=os.environ.get("SITE_TAGLINE", "日本代購・集運・批發一站完成"),
        ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin1234"),
        SUPPORT_EMAIL=os.environ.get("SUPPORT_EMAIL", "service@example.com"),
        SUPPORT_HOURS="週一至週五 9:00 - 17:00",
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(dbm.close_db)
    dbm.init_db(app)
    with app.app_context():
        seed(get_db(), app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])

    register(app)
    return app


# ---------------------------------------------------------------- helpers

def current_user():
    if "user" not in g:
        uid = session.get("uid")
        g.user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None
    return g.user


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not current_user():
            flash("請先登入", "warn")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        u = current_user()
        if not u or not u["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


def rate():
    return float(get_setting("rate_jpy_twd", "0.215"))


def jpy_to_twd(jpy):
    return int(round(jpy * rate()))


def rules():
    return load_rules(get_setting("shipping_rules"))


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def unpaid_twd(user_id):
    rows = get_db().execute("SELECT currency, amount FROM bills WHERE user_id=? AND status='未付款'",
                            (user_id,)).fetchall()
    return sum(r["amount"] if r["currency"] == "TWD" else jpy_to_twd(r["amount"]) for r in rows)


def over_credit(user):
    """True when the member's unpaid bills exceed their credit line."""
    return unpaid_twd(user["id"]) > user["credit_twd"]


def add_bill(db, user_id, kind, currency, amount, ref, hours):
    due = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")
    db.execute("INSERT INTO bills(user_id,kind,currency,amount,ref,due) VALUES(?,?,?,?,?,?)",
               (user_id, kind, currency, amount, ref, due))


def move_money(db, user_id, currency, amount, memo):
    col = "bal_twd" if currency == "TWD" else "bal_jpy"
    db.execute(f"UPDATE users SET {col}={col}+? WHERE id=?", (amount, user_id))
    db.execute("INSERT INTO ledger(user_id,currency,amount,memo) VALUES(?,?,?,?)",
               (user_id, currency, amount, memo))


# ---------------------------------------------------------------- routes

def register(app):

    @app.before_request
    def csrf_protect():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method == "POST" and not app.config.get("TESTING_NO_CSRF"):
            if request.form.get("csrf") != session["csrf"]:
                abort(400, "表單已過期，請重新整理頁面")

    @app.context_processor
    def inject():
        cats = {}
        for a in get_db().execute(f"SELECT category, slug, title FROM articles WHERE is_faq=0 ORDER BY {DOC_ORDER}"):
            cats.setdefault(a["category"], []).append(a)
        return {"me": current_user(), "csrf": session.get("csrf", ""), "doc_nav": cats,
                "site": app.config, "now": datetime.now()}

    # Globals (unlike context-processor values) reach macros imported from _ui.html.
    app.jinja_env.globals["csrf_token"] = lambda: session.get("csrf", "")

    @app.template_filter("money")
    def money(v, cur="TWD"):
        v = v or 0
        return f"NT$ {v:,}" if cur == "TWD" else f"¥ {v:,}"

    @app.template_filter("markdown")
    def markdown_filter(text):
        return Markup(md.markdown(text or "", extensions=["tables"]))

    # ---- public -------------------------------------------------------
    @app.route("/")
    def home():
        db = get_db()
        news = db.execute("SELECT * FROM announcements ORDER BY important DESC, id DESC LIMIT 6").fetchall()
        faqs = db.execute("SELECT * FROM articles WHERE is_faq=1 ORDER BY sort").fetchall()
        return render_template("home.html", news=news, faqs=faqs, rules=rules())

    @app.route("/news")
    def news_list():
        items = get_db().execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
        return render_template("news.html", items=items)

    @app.route("/news/<int:nid>")
    def news_detail(nid):
        item = get_db().execute("SELECT * FROM announcements WHERE id=?", (nid,)).fetchone() or abort(404)
        return render_template("news_detail.html", item=item)

    @app.route("/calculator")
    def calculator():
        return render_template("calculator.html", rules=rules())

    @app.route("/api/shipping-fee")
    def api_fee():
        try:
            w = float(request.args.get("weight", ""))
            r = rules()
            if w > r.get("max_kg", 35):
                return jsonify(ok=False, error=f"單件重量上限 {r.get('max_kg', 35)} 公斤，請聯絡客服")
            fee = shipping_fee(w, r)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="請輸入大於 0 的重量（公斤）"), 400
        return jsonify(ok=True, weight=w, fee=fee, currency="TWD",
                       line=r.get("line"), lead_time=r.get("lead_time"))

    @app.route("/help")
    def help_index():
        faqs = get_db().execute("SELECT * FROM articles WHERE is_faq=1 ORDER BY sort").fetchall()
        return render_template("docs/index.html", faqs=faqs)

    @app.route("/help/<slug>")
    def doc(slug):
        db = get_db()
        art = db.execute("SELECT * FROM articles WHERE slug=?", (slug,)).fetchone() or abort(404)
        order = db.execute(f"SELECT slug, title FROM articles WHERE is_faq=0 ORDER BY {DOC_ORDER}").fetchall()
        slugs = [r["slug"] for r in order]
        i = slugs.index(slug) if slug in slugs else -1
        prev = order[i - 1] if i > 0 else None
        nxt = order[i + 1] if 0 <= i < len(order) - 1 else None
        return render_template("docs/article.html", art=art, prev=prev, nxt=nxt)

    # ---- auth ---------------------------------------------------------
    @app.route("/register", methods=["GET", "POST"])
    def register_view():
        if request.method == "POST":
            f = request.form
            email, name, pw = f.get("email", "").strip().lower(), f.get("name", "").strip(), f.get("password", "")
            errors = {}
            if "@" not in email:
                errors["email"] = "請輸入有效的電子郵件"
            if not name:
                errors["name"] = "請輸入姓名"
            if len(pw) < 8:
                errors["password"] = "密碼至少 8 碼"
            if not f.get("agree"):
                errors["agree"] = "請閱讀並同意服務協議"
            db = get_db()
            if not errors and db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                errors["email"] = "這個電子郵件已經註冊過"
            if errors:
                return render_template("auth/register.html", errors=errors, form=f), 400
            db.execute("INSERT INTO users(email,pw_hash,name,phone,member_code,credit_twd) VALUES(?,?,?,?,?,?)",
                       (email, generate_password_hash(pw), name, f.get("phone", "").strip(),
                        dbm.new_member_code(db), 3000))
            db.commit()
            session.clear()
            session["uid"] = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
            flash("註冊成功！這是你的專屬倉庫地址。", "ok")
            return redirect(url_for("member_home"))
        return render_template("auth/register.html", errors={}, form={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            u = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not u or not check_password_hash(u["pw_hash"], request.form.get("password", "")):
                msg = "電子郵件或密碼不正確"
                return render_template("auth/login.html", email=email,
                                       errors={"form": msg, "email": msg, "password": msg}), 400
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("admin_home" if u["is_admin"] else "member_home"))
        return render_template("auth/login.html", errors={}, email="")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("home"))

    # ---- member -------------------------------------------------------
    @app.route("/member")
    @login_required
    def member_home():
        db, u = get_db(), current_user()
        stats = {
            "purchases": db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND status='待採購'", (u["id"],)).fetchone()[0],
            "in_stock": db.execute("SELECT COUNT(*) FROM parcels WHERE user_id=? AND status='已入庫'", (u["id"],)).fetchone()[0],
            "shipping": db.execute("SELECT COUNT(*) FROM shipments WHERE user_id=? AND status NOT IN ('已送達','已取消')", (u["id"],)).fetchone()[0],
            "unpaid": db.execute("SELECT COUNT(*) FROM bills WHERE user_id=? AND status='未付款'", (u["id"],)).fetchone()[0],
        }
        return render_template("member/home.html", stats=stats,
                               address=get_setting("warehouse_address"), wphone=get_setting("warehouse_phone"))

    @app.route("/member/purchases", methods=["GET", "POST"])
    @login_required
    def member_purchases():
        db, u = get_db(), current_user()
        errors, form = {}, {}
        if request.method == "POST":
            form = request.form
            url_ = form.get("url", "").strip()
            qty = to_int(form.get("qty"), 0)
            price = to_int(form.get("price_jpy"), -1)
            if not url_.startswith(("http://", "https://")):
                errors["url"] = "請貼上商品網址（http 開頭）"
            if qty < 1:
                errors["qty"] = "數量至少 1"
            if price < 0:
                errors["price_jpy"] = "請輸入商品單價（日圓）"
            if not errors and over_credit(u):
                errors["form"] = "未付款帳單已超過信用額度，請先付款再提交採購單"
            if not errors:
                db.execute("INSERT INTO purchases(user_id,url,title,spec,qty,price_jpy,mode,note) VALUES(?,?,?,?,?,?,?,?)",
                           (u["id"], url_, form.get("title", "").strip(), form.get("spec", "").strip(), qty, price,
                            form.get("mode", "網路採購"), form.get("note", "").strip()))
                db.commit()
                flash("採購單已提交，買手會盡快處理", "ok")
                return redirect(url_for("member_purchases"))
        rows = db.execute("SELECT * FROM purchases WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
        return render_template("member/purchases.html", rows=rows, errors=errors, form=form,
                               status=request.args.get("status", ""))

    @app.route("/member/parcels", methods=["GET", "POST"])
    @login_required
    def member_parcels():
        db, u = get_db(), current_user()
        errors, form = {}, {}
        if request.method == "POST":
            form = request.form
            if not form.get("tracking", "").strip():
                errors["tracking"] = "請輸入日本物流單號"
            if not form.get("content", "").strip():
                errors["content"] = "請簡述內容物，報關需要"
            if not errors:
                db.execute("INSERT INTO parcels(user_id,carrier,tracking,content,value_jpy) VALUES(?,?,?,?,?)",
                           (u["id"], form.get("carrier", ""), form["tracking"].strip(), form["content"].strip(),
                            to_int(form.get("value_jpy"))))
                db.commit()
                flash("包裹預報完成，到倉後會通知你", "ok")
                return redirect(url_for("member_parcels"))
        rows = db.execute("SELECT * FROM parcels WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
        return render_template("member/parcels.html", rows=rows, errors=errors, form=form)

    @app.route("/member/shipments", methods=["GET", "POST"])
    @login_required
    def member_shipments():
        db, u = get_db(), current_user()
        errors, form = {}, {}
        stock = db.execute("SELECT * FROM parcels WHERE user_id=? AND status='已入庫' ORDER BY id", (u["id"],)).fetchall()
        if request.method == "POST":
            form = request.form
            ids = [to_int(i) for i in form.getlist("parcel")]
            valid = {p["id"] for p in stock}
            if not ids or any(i not in valid for i in ids):
                errors["parcel"] = "請勾選至少一個已入庫的包裹"
            for key, label in (("recipient", "收件人"), ("phone", "電話"), ("address", "地址")):
                if not form.get(key, "").strip():
                    errors[key] = f"請輸入{label}"
            if not errors and over_credit(u):
                errors["form"] = "未付款帳單已超過信用額度，請先付款再申請出貨"
            if not errors:
                est = sum((p["weight"] or 0) for p in stock if p["id"] in ids)
                cur = db.execute("INSERT INTO shipments(user_id,recipient,phone,address,note,weight) VALUES(?,?,?,?,?,?)",
                                 (u["id"], form["recipient"].strip(), form["phone"].strip(), form["address"].strip(),
                                  form.get("note", "").strip(), est or None))
                for i in ids:
                    db.execute("INSERT INTO shipment_items VALUES(?,?)", (cur.lastrowid, i))
                    db.execute("UPDATE parcels SET status='出貨中' WHERE id=?", (i,))
                db.commit()
                flash("出貨申請已提交，打包秤重後會產生運費帳單", "ok")
                return redirect(url_for("member_shipments"))
        rows = db.execute("SELECT * FROM shipments WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
        return render_template("member/shipments.html", rows=rows, stock=stock, errors=errors,
                               form=form or {"recipient": u["name"], "phone": u["phone"]}, rules=rules())

    @app.route("/member/bills")
    @login_required
    def member_bills():
        u = current_user()
        rows = get_db().execute("SELECT * FROM bills WHERE user_id=? ORDER BY status='已付款', id DESC", (u["id"],)).fetchall()
        return render_template("member/bills.html", rows=rows, rate=rate(), jpy_to_twd=jpy_to_twd)

    @app.route("/member/bills/<int:bid>/pay", methods=["POST"])
    @login_required
    def pay_bill(bid):
        db, u = get_db(), current_user()
        b = db.execute("SELECT * FROM bills WHERE id=? AND user_id=?", (bid, u["id"])).fetchone() or abort(404)
        if b["status"] != "未付款":
            flash("這張帳單已經付過了", "warn")
            return redirect(url_for("member_bills"))
        pay_cur = request.form.get("currency", b["currency"])
        if b["currency"] == "TWD" and pay_cur != "TWD":
            pay_cur = "TWD"  # shipping bills are TWD only
        amount = b["amount"] if pay_cur == b["currency"] else jpy_to_twd(b["amount"])
        balance = u["bal_twd"] if pay_cur == "TWD" else u["bal_jpy"]
        if balance < amount:
            flash(f"{'台幣' if pay_cur == 'TWD' else '日圓'}餘額不足，請先儲值", "warn")
            return redirect(url_for("member_wallet"))
        move_money(db, u["id"], pay_cur, -amount, f"支付{b['kind']}帳單 #{b['id']}")
        db.execute("UPDATE bills SET status='已付款', paid=datetime('now','localtime') WHERE id=?", (bid,))
        if b["kind"] == "運費" and b["ref"].startswith("S"):
            db.execute("UPDATE shipments SET status='已付款' WHERE id=? AND status='待付款'", (to_int(b["ref"][1:]),))
        db.commit()
        flash("付款完成", "ok")
        return redirect(url_for("member_bills"))

    @app.route("/member/wallet", methods=["GET", "POST"])
    @login_required
    def member_wallet():
        db, u = get_db(), current_user()
        errors, form = {}, request.form
        if request.method == "POST":
            cur = request.form.get("currency")
            amt = to_int(request.form.get("amount"))
            last5 = request.form.get("last5", "").strip()
            if cur not in CURRENCIES:
                errors["currency"] = "請選擇幣別"
            if amt <= 0:
                errors["amount"] = "請輸入匯款金額"
            if not (last5.isdigit() and len(last5) == 5):
                errors["last5"] = "請輸入 5 位數字"
            if not errors:
                db.execute("INSERT INTO topups(user_id,currency,amount,account_last5) VALUES(?,?,?,?)",
                           (u["id"], cur, amt, last5))
                db.commit()
                flash("儲值申請已送出，確認入帳後會更新餘額", "ok")
                return redirect(url_for("member_wallet"))
        topups = db.execute("SELECT * FROM topups WHERE user_id=? ORDER BY id DESC LIMIT 20", (u["id"],)).fetchall()
        ledger = db.execute("SELECT * FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
        return render_template("member/wallet.html", topups=topups, ledger=ledger, errors=errors, form=form,
                               bank_twd=get_setting("bank_twd"), bank_jpy=get_setting("bank_jpy"),
                               unpaid=unpaid_twd(u["id"]))

    @app.route("/member/profile", methods=["GET", "POST"])
    @login_required
    def member_profile():
        db, u = get_db(), current_user()
        errors = {}
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                errors["name"] = "請輸入姓名"
            newpw = request.form.get("new_password", "")
            if newpw and len(newpw) < 8:
                errors["new_password"] = "密碼至少 8 碼"
            if not errors:
                db.execute("UPDATE users SET name=?, phone=? WHERE id=?", (name, request.form.get("phone", "").strip(), u["id"]))
                if newpw:
                    db.execute("UPDATE users SET pw_hash=? WHERE id=?", (generate_password_hash(newpw), u["id"]))
                db.commit()
                flash("資料已更新", "ok")
                return redirect(url_for("member_profile"))
        return render_template("member/profile.html", errors=errors)

    # ---- admin --------------------------------------------------------
    @app.route("/admin")
    @admin_required
    def admin_home():
        db = get_db()
        q = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
        stats = {
            "purchases": q("SELECT COUNT(*) FROM purchases WHERE status='待採購'"),
            "parcels": q("SELECT COUNT(*) FROM parcels WHERE status='預報中'"),
            "weigh": q("SELECT COUNT(*) FROM shipments WHERE status='待秤重'"),
            "ship": q("SELECT COUNT(*) FROM shipments WHERE status='已付款'"),
            "topups": q("SELECT COUNT(*) FROM topups WHERE status='待確認'"),
            "members": q("SELECT COUNT(*) FROM users WHERE is_admin=0"),
        }
        return render_template("admin/home.html", stats=stats)

    @app.route("/admin/purchases", methods=["GET", "POST"])
    @admin_required
    def admin_purchases():
        db = get_db()
        if request.method == "POST":
            p = db.execute("SELECT * FROM purchases WHERE id=?", (to_int(request.form.get("id")),)).fetchone() or abort(404)
            action = request.form.get("action")
            if action == "bought" and p["status"] == "待採購":
                price = to_int(request.form.get("price_jpy"), p["price_jpy"])
                ship = to_int(request.form.get("jp_ship_jpy"))
                db.execute("UPDATE purchases SET status='已採購', price_jpy=?, jp_ship_jpy=?, admin_note=? WHERE id=?",
                           (price, ship, request.form.get("admin_note", ""), p["id"]))
                add_bill(db, p["user_id"], "商品", "JPY", price * p["qty"] + ship, f"P{p['id']}", 72)
                flash(f"採購單 #{p['id']} 已採購，商品帳單已產生", "ok")
            elif action == "arrived" and p["status"] == "已採購":
                w = float(request.form.get("weight") or 0) or None
                db.execute("UPDATE purchases SET status='已入庫' WHERE id=?", (p["id"],))
                db.execute("INSERT INTO parcels(user_id,carrier,tracking,content,value_jpy,weight,status,purchase_id,received) "
                           "VALUES(?,?,?,?,?,?,'已入庫',?,datetime('now','localtime'))",
                           (p["user_id"], "代採購", f"P{p['id']}", p["title"] or p["url"][:60],
                            p["price_jpy"] * p["qty"], w, p["id"]))
                flash(f"採購單 #{p['id']} 已入庫", "ok")
            elif action == "cancel" and p["status"] == "待採購":
                db.execute("UPDATE purchases SET status='已取消', admin_note=? WHERE id=?",
                           (request.form.get("admin_note", ""), p["id"]))
                flash(f"採購單 #{p['id']} 已取消", "ok")
            else:
                flash("這個狀態不能執行這個動作", "warn")
            db.commit()
            return redirect(url_for("admin_purchases", status=request.args.get("status", "")))
        status = request.args.get("status", "待採購")
        rows = db.execute("SELECT p.*, u.member_code, u.name FROM purchases p JOIN users u ON u.id=p.user_id "
                          "WHERE (?='' OR p.status=?) ORDER BY p.id DESC", (status, status)).fetchall()
        return render_template("admin/purchases.html", rows=rows, status=status, flow=PURCHASE_FLOW)

    @app.route("/admin/parcels", methods=["GET", "POST"])
    @admin_required
    def admin_parcels():
        db = get_db()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "receive":
                pid = to_int(request.form.get("id"))
                w = float(request.form.get("weight") or 0)
                if w <= 0:
                    flash("請輸入重量", "warn")
                else:
                    db.execute("UPDATE parcels SET status='已入庫', weight=?, received=datetime('now','localtime') "
                               "WHERE id=? AND status='預報中'", (w, pid))
                    flash(f"包裹 #{pid} 已入庫", "ok")
            elif action == "unclaimed":
                code = request.form.get("member_code", "").strip().upper()
                u = db.execute("SELECT id FROM users WHERE member_code=?", (code,)).fetchone()
                w = float(request.form.get("weight") or 0)
                if not u or w <= 0:
                    flash("找不到會員編號，或重量未填", "warn")
                else:
                    db.execute("INSERT INTO parcels(user_id,carrier,tracking,content,weight,status,received) "
                               "VALUES(?,?,?,?,?,'已入庫',datetime('now','localtime'))",
                               (u["id"], request.form.get("carrier", ""), request.form.get("tracking", ""),
                                request.form.get("content", "未預報包裹"), w))
                    flash("包裹已登記入庫", "ok")
            db.commit()
            return redirect(url_for("admin_parcels", status=request.args.get("status", "")))
        status = request.args.get("status", "預報中")
        rows = db.execute("SELECT p.*, u.member_code, u.name FROM parcels p JOIN users u ON u.id=p.user_id "
                          "WHERE (?='' OR p.status=?) ORDER BY p.id DESC", (status, status)).fetchall()
        return render_template("admin/parcels.html", rows=rows, status=status,
                               flow=["預報中", "已入庫", "出貨中", "已出貨"])

    @app.route("/admin/shipments", methods=["GET", "POST"])
    @admin_required
    def admin_shipments():
        db = get_db()
        if request.method == "POST":
            s = db.execute("SELECT * FROM shipments WHERE id=?", (to_int(request.form.get("id")),)).fetchone() or abort(404)
            action = request.form.get("action")
            if action == "weigh" and s["status"] == "待秤重":
                try:
                    w = float(request.form.get("weight"))
                    fee = shipping_fee(w, rules()) + to_int(request.form.get("extra"))
                except (TypeError, ValueError):
                    flash("請輸入正確的重量", "warn")
                    return redirect(url_for("admin_shipments", status="待秤重"))
                db.execute("UPDATE shipments SET weight=?, fee_twd=?, status='待付款' WHERE id=?", (w, fee, s["id"]))
                add_bill(db, s["user_id"], "運費", "TWD", fee, f"S{s['id']}", 48)
                flash(f"出貨單 #{s['id']} 運費 NT$ {fee:,}，帳單已產生", "ok")
            elif action == "ship" and s["status"] == "已付款":
                db.execute("UPDATE shipments SET status='已出貨', tracking=? WHERE id=?",
                           (request.form.get("tracking", ""), s["id"]))
                db.execute("UPDATE parcels SET status='已出貨' WHERE id IN (SELECT parcel_id FROM shipment_items WHERE shipment_id=?)", (s["id"],))
                flash(f"出貨單 #{s['id']} 已出貨", "ok")
            elif action == "deliver" and s["status"] == "已出貨":
                db.execute("UPDATE shipments SET status='已送達' WHERE id=?", (s["id"],))
                flash(f"出貨單 #{s['id']} 已送達", "ok")
            else:
                flash("這個狀態不能執行這個動作", "warn")
            db.commit()
            return redirect(url_for("admin_shipments", status=request.args.get("status", "")))
        status = request.args.get("status", "待秤重")
        rows = db.execute("SELECT s.*, u.member_code, u.name, "
                          "(SELECT COUNT(*) FROM shipment_items i WHERE i.shipment_id=s.id) AS n "
                          "FROM shipments s JOIN users u ON u.id=s.user_id "
                          "WHERE (?='' OR s.status=?) ORDER BY s.id DESC", (status, status)).fetchall()
        return render_template("admin/shipments.html", rows=rows, status=status, flow=SHIPMENT_FLOW)

    @app.route("/admin/topups", methods=["GET", "POST"])
    @admin_required
    def admin_topups():
        db = get_db()
        if request.method == "POST":
            t = db.execute("SELECT * FROM topups WHERE id=? AND status='待確認'",
                           (to_int(request.form.get("id")),)).fetchone() or abort(404)
            if request.form.get("action") == "approve":
                db.execute("UPDATE topups SET status='已入帳' WHERE id=?", (t["id"],))
                move_money(db, t["user_id"], t["currency"], t["amount"], f"儲值 #{t['id']}")
                flash(f"儲值 #{t['id']} 已入帳", "ok")
            else:
                db.execute("UPDATE topups SET status='已退回' WHERE id=?", (t["id"],))
                flash(f"儲值 #{t['id']} 已退回", "ok")
            db.commit()
            return redirect(url_for("admin_topups"))
        rows = db.execute("SELECT t.*, u.member_code, u.name FROM topups t JOIN users u ON u.id=t.user_id "
                          "ORDER BY t.status!='待確認', t.id DESC LIMIT 200").fetchall()
        return render_template("admin/topups.html", rows=rows)

    @app.route("/admin/members", methods=["GET", "POST"])
    @admin_required
    def admin_members():
        db = get_db()
        if request.method == "POST":
            db.execute("UPDATE users SET credit_twd=? WHERE id=?",
                       (max(0, to_int(request.form.get("credit_twd"))), to_int(request.form.get("id"))))
            db.commit()
            flash("信用額度已更新", "ok")
            return redirect(url_for("admin_members"))
        rows = db.execute("SELECT * FROM users WHERE is_admin=0 ORDER BY id DESC").fetchall()
        return render_template("admin/members.html", rows=rows)

    @app.route("/admin/content", methods=["GET", "POST"])
    @admin_required
    def admin_content():
        db = get_db()
        if request.method == "POST":
            kind = request.form.get("kind")
            if kind == "news":
                if request.form.get("delete"):
                    db.execute("DELETE FROM announcements WHERE id=?", (to_int(request.form.get("id")),))
                elif request.form.get("title", "").strip():
                    db.execute("INSERT INTO announcements(title,body,important) VALUES(?,?,?)",
                               (request.form["title"].strip(), request.form.get("body", ""),
                                1 if request.form.get("important") else 0))
            elif kind == "article":
                aid = to_int(request.form.get("id"))
                fields = (request.form.get("category", "").strip(), request.form.get("title", "").strip(),
                          request.form.get("body", ""), to_int(request.form.get("sort")),
                          1 if request.form.get("is_faq") else 0)
                if not fields[0] or not fields[1]:
                    flash("分類與標題必填", "warn")
                    return redirect(url_for("admin_content", edit=aid or None))
                if aid:
                    db.execute("UPDATE articles SET category=?, title=?, body=?, sort=?, is_faq=?, "
                               "updated=datetime('now','localtime') WHERE id=?", (*fields, aid))
                else:
                    slug = request.form.get("slug", "").strip() or f"a{secrets.token_hex(3)}"
                    db.execute("INSERT INTO articles(category,title,body,sort,is_faq,slug) VALUES(?,?,?,?,?,?)",
                               (*fields, slug))
            db.commit()
            flash("內容已儲存", "ok")
            return redirect(url_for("admin_content"))
        edit = db.execute("SELECT * FROM articles WHERE id=?", (to_int(request.args.get("edit")),)).fetchone()
        return render_template("admin/content.html", edit=edit,
                               news=db.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall(),
                               articles=db.execute("SELECT * FROM articles ORDER BY is_faq, category, sort").fetchall())

    @app.route("/admin/settings", methods=["GET", "POST"])
    @admin_required
    def admin_settings():
        import json
        error = None
        if request.method == "POST":
            try:
                parsed = json.loads(request.form.get("shipping_rules", ""))
                shipping_fee(1, parsed)
                float(request.form.get("rate_jpy_twd", ""))
            except (ValueError, KeyError, TypeError, IndexError):
                error = "匯率或運費規則格式不正確，未儲存"
            else:
                for k in ("rate_jpy_twd", "warehouse_address", "warehouse_phone", "bank_twd", "bank_jpy"):
                    set_setting(k, request.form.get(k, "").strip())
                set_setting("shipping_rules", json.dumps(parsed, ensure_ascii=False))
                flash("設定已儲存", "ok")
                return redirect(url_for("admin_settings"))
        keys = ("rate_jpy_twd", "warehouse_address", "warehouse_phone", "bank_twd", "bank_jpy")
        values = {k: get_setting(k) for k in keys}
        values["shipping_rules"] = json.dumps(rules(), ensure_ascii=False, indent=2)
        if request.method == "POST":
            values.update(request.form.to_dict())
        errors = {"form": error, "rate_jpy_twd": error, "shipping_rules": error} if error else {}
        return render_template("admin/settings.html", values=values, errors=errors)

    @app.errorhandler(403)
    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=e.code), e.code


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
