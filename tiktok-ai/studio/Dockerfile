FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk fonts-wqy-zenhei fontconfig \
    && rm -rf /var/lib/apt/lists/* && fc-cache -f
WORKDIR /app
COPY requirements.txt /app/studio/requirements.txt
RUN pip install --no-cache-dir -r /app/studio/requirements.txt
COPY . /app/studio
ENV STUDIO_OUTPUT_DIR=/data/output STUDIO_WORK_DIR=/data/work PORT=7860 SUBTITLE_FONT="Noto Sans CJK TC"
EXPOSE 7860
CMD ["python", "-m", "studio.server"]
