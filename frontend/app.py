import streamlit as st
import requests
import json
import uuid

API_BASE_URL = "http://host.docker.internal:8000"

st.set_page_config(page_title="RAG 知识库问答", page_icon="📚", layout="wide")

# ---------- 初始化 session state ----------
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = set()


def get_headers():
    """返回带认证 Token 的请求头"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def handle_401(response):
    """处理 401 未授权，清空登录状态并刷新"""
    if response.status_code == 401:
        st.error("登录已过期，请重新登录")
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()


# ---------- 登录/注册界面 ----------
if not st.session_state.token:
    st.title("🔐 登录 / 注册")
    tab1, tab2 = st.tabs(["登录", "注册"])

    with tab1:
        username = st.text_input("用户名", key="login_username")
        password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录"):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/auth/login",
                    json={"username": username, "password": password}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user = username
                    st.rerun()
                else:
                    st.error("登录失败，请检查用户名密码")
            except Exception as e:
                st.error(f"连接失败: {e}")

    with tab2:
        new_username = st.text_input("用户名", key="reg_username")
        new_email = st.text_input("邮箱", key="reg_email")
        new_password = st.text_input("密码", type="password", key="reg_password")
        if st.button("注册"):
            try:
                # 直接从session_state里取值
                username_val = st.session_state.reg_username
                email_val = st.session_state.reg_email
                password_val = st.session_state.reg_password

                resp = requests.post(
                    f"{API_BASE_URL}/auth/register",
                    json={
                        "username": username_val,
                        "email": email_val,
                        "password": password_val
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user = username_val
                    st.rerun()
                else:
                    st.error(f"注册失败: {resp.text}")
            except Exception as e:
                st.error(f"连接失败: {e}")
    st.stop()


# ---------- 已登录主界面 ----------
st.sidebar.write(f"👤 {st.session_state.user}")
if st.sidebar.button("登出"):
    # 清空所有用户相关状态
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.messages = []
    st.session_state.uploaded_files = set()
    st.session_state.session_id = str(uuid.uuid4())
    st.rerun()

# 侧边栏：文档管理
with st.sidebar:
    st.header("📁 文档管理")

    uploaded_file = st.file_uploader(
        "上传文档 (PDF/DOCX/TXT/MD)",
        type=["pdf", "docx", "txt", "md"]
    )

    if uploaded_file:
        if uploaded_file.name in st.session_state.uploaded_files:
            st.success(f"✅ {uploaded_file.name} 已处理完成")
        else:
            with st.spinner("上传中..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                resp = requests.post(
                    f"{API_BASE_URL}/documents/upload",
                    files=files,
                    headers=get_headers()
                )
                if resp.status_code == 200:
                    st.success(f"✅ {uploaded_file.name} 上传成功，正在后台处理...")
                    st.session_state.uploaded_files.add(uploaded_file.name)
                else:
                    handle_401(resp)
                    if resp.status_code != 401:
                        st.error(f"上传失败: {resp.text}")

    st.subheader("已上传文档")
    try:
        resp = requests.get(
            f"{API_BASE_URL}/documents/",
            headers=get_headers()
        )
        if resp.status_code == 200:
            docs = resp.json()
            # 使用字典按 id 去重（保留最新状态）
            unique_docs = {doc["id"]: doc for doc in docs}.values()
            for doc in docs:
                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "uploaded": "📤",
                    "parsing": "📄",
                    "chunking": "✂️",
                    "embedding": "🧮"
                }.get(doc["status"], "⏳")
                st.text(f"{status_emoji} {doc['filename']} ({doc['status']})")
        else:
            handle_401(resp)
    except Exception as e:
        st.warning("无法获取文档列表")

# 主界面：对话区域
st.title("📚 RAG 知识库问答系统")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg:
            with st.expander("📖 引用来源"):
                for src in msg["sources"]:
                    st.markdown(
                        f"- 文档 {src['document_id']}: {src['content']} "
                        f"(相似度: {src['similarity']:.3f})"
                    )

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        sources = []

        try:
            resp = requests.post(
                f"{API_BASE_URL}/chat/",
                json={
                    "query": prompt,
                    "session_id": st.session_state.session_id,
                    "stream": True
                },
                stream=True,
                headers=get_headers(),
                timeout=(10,90)  # 增加超时
            )

            if resp.status_code == 200:
                sources = []
                for line in resp.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if "content" in data:
                                        full_response += data["content"]
                                        message_placeholder.markdown(full_response + "▌")
                                    elif "sources" in data:
                                        sources = data["sources"]
                                except json.JSONDecodeError:
                                    pass

                message_placeholder.markdown(full_response)

                if sources:
                    with st.expander("📖 引用来源"):
                        for src in sources:
                            st.markdown(
                                f"- 文档 {src['document_id']}: {src['content']} "
                                f"(相似度: {src['similarity']:.3f})"
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "sources": sources
                })
            else:
                handle_401(resp)
                if resp.status_code != 401:
                    st.error(f"请求失败: {resp.text}")
        except Exception as e:
            st.error(f"调用失败: {str(e)}")

# 侧边栏底部：会话管理
with st.sidebar:
    st.divider()
    st.subheader("💬 会话管理")
    if st.button("🔄 开始新会话"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.caption(f"当前会话 ID: {st.session_state.session_id[:8]}...")