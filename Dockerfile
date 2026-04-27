FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制 entrypoint 脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 复制应用代码
COPY . .

# 创建上传目录
RUN mkdir -p /app/uploads

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
