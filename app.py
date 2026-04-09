from flask import Flask, request, jsonify, send_from_directory
import pdfplumber, re, unicodedata, os, tempfile

app = Flask(__name__, static_folder='static', static_url_path='')

def nfkc(s):
    return unicodedata.normalize('NFKC', s)

def parse_pdf(path):
    orders = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            text = nfkc(text)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            o = {'logistics': '', 'items': []}
            in_items = False

            def find(pat, s):
                m = re.search(pat, s or '')
                return m.group(1).strip() if m else None

            for l in lines:
                if l == '出貨明細':
                    continue
                if '訂單編號' in l:
                    o['order_id'] = find(r'訂單編號[:：]\s*(\S+)', l)
                if '物流編號' in l:
                    o['logistics'] = find(r'物流編號[:：]\s*(\d+)', l) or ''
                if '訂購日期' in l:
                    v = find(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', l)
                    if v: o['date'] = v
                if '收件人' in l and '電話' not in l:
                    v = find(r'收件人[:：]\s*(\S+)', l)
                    if v: o['recipient'] = v
                if '收件人電話' in l:
                    v = find(r'收件人電話[:：]\s*(\S+)', l)
                    if v: o['rec_phone'] = v
                if '付款方式' in l:
                    v = find(r'付款方式[:：]\s*(.+?)(?:\s{2,}|$)', l)
                    if v: o['payment'] = v.strip()
                if '送貨地址' in l:
                    v = find(r'送貨地址[:：]\s*(.+?)(?:\s{2,}|$)', l)
                    if v: o['address'] = v.strip()
                if '門市名稱' in l:
                    v = find(r'門市名稱[:：]\s*(.+)', l)
                    if v: o['store'] = v.strip()
                if '商品總數量' in l:
                    v = find(r'商品總數量[:：]\s*(\d+)', l)
                    if v: o['qty'] = int(v)
                if re.match(r'^總計[:：]', l):
                    v = find(r'NT\s*\$\s*([\d,]+)', l)
                    if v: o['total'] = 'NT$' + v.replace(',', '')
                if re.match(r'^品名\s+單價', l):
                    in_items = True
                    continue
                if re.match(r'^(商品總數量|運費|額外運費|總計)', l):
                    in_items = False
                if in_items:
                    m = re.match(r'^(.+?)\s+(\d+)\s+(\d+)\s+(\d+)$', l)
                    if m:
                        o['items'].append({
                            'name': m[1].strip(),
                            'price': int(m[2]),
                            'qty': int(m[3]),
                            'sub': int(m[4])
                        })
            if o.get('order_id'):
                orders.append(o)
    return orders

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files:
        return jsonify({'error': '請上傳 PDF 檔案'}), 400
    f = request.files['pdf']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'error': '只接受 PDF 格式'}), 400

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        f.save(tmp.name)
        try:
            orders = parse_pdf(tmp.name)
        except Exception as e:
            return jsonify({'error': f'解析失敗：{str(e)}'}), 500
        finally:
            os.unlink(tmp.name)

    if not orders:
        return jsonify({'error': '找不到訂單，請確認是 BVSHOP 出貨明細 PDF'}), 400

    return jsonify({'orders': orders, 'count': len(orders)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
