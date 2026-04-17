import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import plotly.express as px
import streamlit.components.v1 as components
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ==========================================
# CẤU HÌNH TRANG GIAO DIỆN
# ==========================================
st.set_page_config(page_title="Hệ Thống Quản Lý Học Vụ & Đồ Án", layout="wide", page_icon="🎓")

# ==========================================
# 1. KẾT NỐI GOOGLE SHEETS & TỐI ƯU API
# ==========================================
@st.cache_resource
def init_connection():
    if "gcp_service_account_json" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp_service_account_json"])
        gc = gspread.service_account_from_dict(creds_dict)
    else:
        gc = gspread.service_account(filename='credentials.json')
    return gc.open("QuanLyDoAn")

# Tuyệt chiêu chống lỗi 429: Lưu bộ nhớ đệm (Cache) cho các trang tính
@st.cache_resource
def get_worksheets():
    sh = init_connection()
    return (
        sh.worksheet("Nhom"),
        sh.worksheet("LichHen"),
        sh.worksheet("BaoCao"),
        sh.worksheet("DanhGia"),
        sh.worksheet("NhiemVu"),
        sh.worksheet("DanhGiaCheo"),
        sh.worksheet("HoiDap"),
        sh.worksheet("ThongBao") 
    )

ws_nhom, ws_lichhen, ws_baocao, ws_danhgia, ws_nhiemvu, ws_peer, ws_hoidap, ws_thongbao = get_worksheets()

def send_email_report(receiver_email, tieu_de_hoac_ten_nhom, noi_dung, is_reminder=False):
    sender_email = st.secrets.get("SENDER_EMAIL", "email_cua_ban@gmail.com") 
    app_password = st.secrets.get("APP_PASSWORD", "mat_khau_ung_dung") 
    msg = MIMEMultipart()
    msg['From'] = f"GV Hướng Dẫn <{sender_email}>"
    msg['To'] = receiver_email
    
    # Xử lý luồng: Nhắc nhở (Không đính kèm) vs Gửi Báo cáo (Có đính kèm)
    if is_reminder:
        # Nếu là email nhắc deadline
        msg['Subject'] = tieu_de_hoac_ten_nhom # Ở đây 'tieu_de_hoac_ten_nhom' đóng vai trò là Tiêu đề Email
        msg.attach(MIMEText(noi_dung, 'plain')) # 'noi_dung' là chữ trơn
    else:
        # Nếu là email gửi biên bản điểm
        msg['Subject'] = f"[Thông báo] Kết quả đánh giá - Đề tài: {tieu_de_hoac_ten_nhom}"
        text_body = f"Chào nhóm {tieu_de_hoac_ten_nhom},\n\nGiảng viên vừa cập nhật kết quả đánh giá cho đồ án của nhóm. Các em tải file Biên bản đính kèm để xem chi tiết nhé.\n\nTrân trọng."
        msg.attach(MIMEText(text_body, 'plain'))
        
        # Tạo file đính kèm HTML
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(noi_dung.encode('utf-8')) # 'noi_dung' lúc này là chuỗi HTML code
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f"attachment; filename= BienBan_{tieu_de_hoac_ten_nhom}.html")
        msg.attach(attachment)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        return True
    except: 
        return False

# ==========================================
# 2. XÁC THỰC VÀ PHÂN QUYỀN (SIDEBAR)
# ==========================================
st.sidebar.header("🔐 Khu Vực Đăng Nhập")
che_do = st.sidebar.radio("Vai trò của bạn:", ["🎓 Sinh viên", "👩‍🏫 Giáo viên (Quản lý)"])

is_authenticated = False
role = None
user_code = ""

# Tải dữ liệu nhóm toàn cục
data_nhom = ws_nhom.get_all_records()
df_nhom_toan_cuc = pd.DataFrame(data_nhom) if data_nhom else pd.DataFrame()

if che_do == "👩‍🏫 Giáo viên (Quản lý)":
    mat_khau_gv = st.sidebar.text_input("Nhập mật khẩu quản trị:", type="password")
    if mat_khau_gv == st.secrets.get("GV_PASSWORD", "123456"): 
        st.sidebar.success("Xác thực thành công!")
        is_authenticated = True
        role = "Giáo viên"
    elif mat_khau_gv:
        st.sidebar.error("Sai mật khẩu!")

elif che_do == "🎓 Sinh viên":
    ma_truy_cap = st.sidebar.text_input("Nhập Mã Truy Cập (Do GV cấp):", type="password")
    if ma_truy_cap:
        if not df_nhom_toan_cuc.empty and 'MaTruyCap' in df_nhom_toan_cuc.columns:
            if ma_truy_cap in df_nhom_toan_cuc['MaTruyCap'].astype(str).unique().tolist():
                st.sidebar.success("Đăng nhập thành công!")
                is_authenticated = True
                role = "Sinh viên"
                user_code = ma_truy_cap
            else: st.sidebar.error("Mã truy cập không tồn tại.")

if not is_authenticated:
    st.title("🎓 Hệ Thống Quản Lý Học Vụ & Đồ Án")
    st.warning("👈 Vui lòng đăng nhập ở thanh công cụ bên trái để sử dụng hệ thống.")
    st.stop()

# ==========================================
# 3. MENU ĐIỀU HƯỚNG
# ==========================================
if role == "Giáo viên":
    menu = ["📊 Dashboard & Quản Lý", "📢 Quản Lý Thông Báo", "➕ Thêm Nhóm Mới", "🕵️ Theo Dõi Tiến Độ & Lịch Hẹn", "📬 Hòm Thư & Đánh Giá", "🎯 Chấm Điểm & Xuất Báo Cáo", "📊 Tiêu Chí Chấm Điểm"]
else: # Vai trò Sinh viên
    menu = [
        "💻 Không Gian Làm Việc Chung", 
        "🏆 Bảng Xếp Hạng",
        "📚 Thư Viện Biểu Mẫu", 
        "🤝 Đánh Giá Chéo", 
        "🆘 Gửi Câu Hỏi Cho GV",
        "🔍 Tra cứu Điểm & Phản hồi"
    ]

choice = st.sidebar.selectbox("Chọn chức năng:", menu)
st.title("🎓 Hệ Thống Quản Lý Học Vụ & Đồ Án")

# ==========================================
# 4. GIAO DIỆN GIÁO VIÊN
# ==========================================
if role == "Giáo viên":
    # --- Hàm hỗ trợ lọc phân cấp cho Giáo viên ---
    def bo_loc_phan_cap(df):
        st.write("**🔍 Bộ lọc tìm kiếm:**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            khoa = st.selectbox("Khóa:", ["Tất cả"] + df['Khoa'].dropna().unique().tolist())
            df1 = df[df['Khoa'] == khoa] if khoa != "Tất cả" else df
        with c2:
            lop = st.selectbox("Lớp:", ["Tất cả"] + df1['Lop'].dropna().unique().tolist())
            df2 = df1[df1['Lop'] == lop] if lop != "Tất cả" else df1
        with c3:
            hp = st.selectbox("Học phần:", ["Tất cả"] + df2['HocPhan'].dropna().unique().tolist())
            df3 = df2[df2['HocPhan'] == hp] if hp != "Tất cả" else df2
        with c4:
            nhom = st.selectbox("Nhóm:", ["Tất cả"] + df3['TenNhom'].dropna().unique().tolist())
            df_final = df3[df3['TenNhom'] == nhom] if nhom != "Tất cả" else df3
        return df_final, nhom

    if choice == "➕ Thêm Nhóm Mới":
        st.header("➕ Thêm Nhóm Đồ Án / Tiểu Luận")
        
        with st.form("form_them_nhom", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1: khoa = st.text_input("Khóa (Vd: K2)")
            with col2: lop = st.text_input("Lớp (Vd: KTĐK&TĐH)")
            with col3: hoc_phan = st.text_input("Học phần (Vd:Đồ án 1)")
            
            ten_nhom = st.text_input("Tên Nhóm (Vd: Nhóm 1)")
            
            danh_sach_sv = st.text_area(
                "Danh sách sinh viên (Họ và Tên - Mã SV):", 
                placeholder="Ví dụ:\n1. Nguyễn Văn A - 20T1020111\n2. Trần Thị B - 20T1020112"
            )
            
            ten_de_tai = st.text_input("Tên đề tài / Hướng nghiên cứu")
            email_nhom = st.text_input("Email đại diện nhóm (Để nhận thông báo)")
            passcode = st.text_input("Mã truy cập (Passcode cho sinh viên đăng nhập)")
            link_docs = st.text_input("Link Google Docs (Quyền Editor để sinh viên làm bài chung)")
            trang_thai = st.selectbox("Trạng thái", ["Mới bắt đầu", "Đang thực hiện", "Chờ nghiệm thu", "Đã hoàn thành"])
            
            if st.form_submit_button("Lưu thông tin Nhóm"):
                if ten_nhom and passcode and danh_sach_sv: 
                    new_id = len(ws_nhom.get_all_values())
                    ws_nhom.append_row([new_id, khoa, lop, hoc_phan, ten_nhom, ten_de_tai, email_nhom, passcode, link_docs, trang_thai, danh_sach_sv])
                    st.success(f"Đã thêm {ten_nhom} thành công!")
                else:
                    st.error("Vui lòng điền đầy đủ Tên nhóm, Mã truy cập và Danh sách sinh viên.")

    elif choice == "📢 Quản Lý Thông Báo":
        st.header("📢 Đăng Tải Thông Báo Chung")
        st.write("Các thông báo đăng tại đây sẽ hiển thị nổi bật trên màn hình của tất cả sinh viên (Các Khóa/Lớp).")
        
        with st.form("form_dang_thong_bao", clear_on_submit=True):
            phan_loai = st.radio("Loại thông báo:", ["Khẩn cấp", "Học vụ", "Hoạt động Đoàn Hội"], horizontal=True)
            tieu_de = st.text_input("Tiêu đề thông báo:")
            noi_dung = st.text_area("Nội dung chi tiết (Ví dụ: Thể lệ hội thi nấu ăn, thời gian tham gia trồng cây, hạn nộp sổ...)")
            
            if st.form_submit_button("Phát Thông Báo"):
                if tieu_de and noi_dung:
                    new_id = len(ws_thongbao.get_all_values())
                    ws_thongbao.append_row([new_id, tieu_de, noi_dung, phan_loai, datetime.now().strftime("%Y-%m-%d %H:%M"), "Hiển thị"])
                    st.success("Đã đăng thông báo thành công!")
                else:
                    st.error("Vui lòng nhập đủ Tiêu đề và Nội dung.")
                    
        st.write("---")
        st.subheader("📋 Các thông báo đang ghim")
        df_tb = pd.DataFrame(ws_thongbao.get_all_records())
        if not df_tb.empty:
            df_hien_thi = df_tb[df_tb['TrangThai'] == "Hiển thị"]
            for idx, row in df_hien_thi.iloc[::-1].iterrows():
                with st.expander(f"[{row['PhanLoai']}] {row['TieuDe']} - {row['ThoiGian']}"):
                    st.write(row['NoiDung'])
                    if st.button("🗑️ Gỡ xuống (Ẩn)", key=f"hide_{idx}"):
                        ws_thongbao.update_cell(idx + 2, 6, "Đã ẩn")
                        st.rerun()

    elif choice == "📊 Dashboard & Quản Lý":
        st.header("📊 Dashboard Thống Kê Tổng Quan")
        if not df_nhom_toan_cuc.empty:
            df_loc, _ = bo_loc_phan_cap(df_nhom_toan_cuc)
            st.write("---")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng số nhóm", len(df_loc))
            c2.metric("Số Học phần", df_loc['HocPhan'].nunique())
            c3.metric("Số Lớp", df_loc['Lop'].nunique())
            c4.metric("Hoàn thành", len(df_loc[df_loc['TrangThai'] == "Hoàn thành"]))
            
            st.dataframe(df_loc[['Khoa', 'Lop', 'HocPhan', 'TenNhom', 'TenDeTai', 'TrangThai']], use_container_width=True)
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                if not df_loc.empty:
                    fig_pie = px.pie(df_loc, names='TrangThai', title="Tỷ Lệ Tiến Độ", hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
                    st.plotly_chart(fig_pie, use_container_width=True)
            with col_chart2:
                if not df_loc.empty:
                    count_hp = df_loc['HocPhan'].value_counts().reset_index()
                    count_hp.columns = ['Học Phần', 'Số Lượng Nhóm']
                    fig_bar = px.bar(count_hp, x='Học Phần', y='Số Lượng Nhóm', title="Phân bổ nhóm theo Học phần", text='Số Lượng Nhóm')
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            # --- BỔ SUNG & SỬA LỖI BẢNG XẾP HẠNG CHO GIÁO VIÊN ---
            st.write("---")
            st.subheader("🏆 Bảng Xếp Hạng Thi Đua Các Nhóm")
            
            df_bc_all = pd.DataFrame(ws_baocao.get_all_records())
            df_nv_all = pd.DataFrame(ws_nhiemvu.get_all_records())
            
            bang_diem_gv = []
            for _, row_nhom in df_loc.iterrows():
                n_id = row_nhom['ID']
                diem_chat = 0
                diem_task = 0
                
                # Tính điểm Chat (Loại trừ các tin nhắn do Giảng viên nhắn để công bằng)
                if not df_bc_all.empty and 'NhomID' in df_bc_all.columns:
                    sv_chat = df_bc_all[(df_bc_all['NhomID'] == n_id) & (~df_bc_all['TenSinhVien'].astype(str).str.contains("Giảng viên", na=False))]
                    diem_chat = len(sv_chat) * 2
                
                # Tính điểm Task đã hoàn thành
                if not df_nv_all.empty and 'NhomID' in df_nv_all.columns:
                    diem_task = len(df_nv_all[(df_nv_all['NhomID'] == n_id) & (df_nv_all['TrangThai'] == 'Đã xong')]) * 10
                    
                tong_diem = diem_chat + diem_task
                
                bang_diem_gv.append({
                    "Mã Nhóm Trục X": f"{row_nhom['TenNhom']} ({row_nhom['Lop']})", # Fix lỗi cộng dồn biểu đồ
                    "Tên Nhóm": row_nhom['TenNhom'],
                    "Lớp": row_nhom['Lop'],
                    "Học Phần": row_nhom['HocPhan'],
                    "Điểm Trao Đổi": diem_chat, # Tách điểm để dễ quản lý
                    "Điểm Nhiệm Vụ": diem_task, # Tách điểm để dễ quản lý
                    "Điểm Năng Nổ": tong_diem
                })
                
            df_bang_diem_gv = pd.DataFrame(bang_diem_gv).sort_values(by="Điểm Năng Nổ", ascending=False).reset_index(drop=True)
            
            if not df_bang_diem_gv.empty and df_bang_diem_gv['Điểm Năng Nổ'].sum() > 0:
                # --- THAY THẾ KHỐI HIỂN THỊ HUY CHƯƠNG TẠI ĐÂY ---
                c1, c2, c3 = st.columns(3)
                if len(df_bang_diem_gv) > 0:
                    c1.success(f"""
                        🥇 **Hạng 1: {df_bang_diem_gv.iloc[0]['Tên Nhóm']}**
                        \n 📘 {df_bang_diem_gv.iloc[0]['Học Phần']}
                        \n 🏫 Lớp: {df_bang_diem_gv.iloc[0]['Lớp']}
                        \n 🔥 {df_bang_diem_gv.iloc[0]['Điểm Năng Nổ']} Điểm
                    """)
                if len(df_bang_diem_gv) > 1:
                    c2.info(f"""
                        🥈 **Hạng 2: {df_bang_diem_gv.iloc[1]['Tên Nhóm']}**
                        \n 📘 {df_bang_diem_gv.iloc[1]['Học Phần']}
                        \n 🏫 Lớp: {df_bang_diem_gv.iloc[1]['Lớp']}
                        \n ⚡ {df_bang_diem_gv.iloc[1]['Điểm Năng Nổ']} Điểm
                    """)
                if len(df_bang_diem_gv) > 2:
                    c3.warning(f"""
                        🥉 **Hạng 3: {df_bang_diem_gv.iloc[2]['Tên Nhóm']}**
                        \n 📘 {df_bang_diem_gv.iloc[2]['Học Phần']}
                        \n 🏫 Lớp: {df_bang_diem_gv.iloc[2]['Lớp']}
                        \n 🌟 {df_bang_diem_gv.iloc[2]['Điểm Năng Nổ']} Điểm
                    """)
                # --- KẾT THÚC ĐOẠN THAY THẾ ---

                # Biểu đồ vẫn giữ nguyên phía dưới...
                fig_ldb = px.bar(df_bang_diem_gv, x="Mã Nhóm Trục X", y="Điểm Năng Nổ", color="Điểm Năng Nổ", text="Điểm Năng Nổ", 
                                 title="Biểu đồ thi đua chi tiết", color_continuous_scale="Viridis", 
                                 hover_data=["Học Phần", "Điểm Trao Đổi", "Điểm Nhiệm Vụ"])
                st.plotly_chart(fig_ldb, use_container_width=True)
                
                # TÍNH NĂNG MỚI: Bảng chi tiết và Nút xuất Excel
                with st.expander("👁️ Xem chi tiết cơ cấu điểm & Xuất file Excel"):
                    st.dataframe(df_bang_diem_gv[['Tên Nhóm', 'Lớp', 'Học Phần', 'Điểm Trao Đổi', 'Điểm Nhiệm Vụ', 'Điểm Năng Nổ']], use_container_width=True)
                    # Dùng utf-8-sig để xuất ra Excel không bị lỗi font tiếng Việt
                    csv = df_bang_diem_gv.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Tải Bảng Điểm Thi Đua (CSV)",
                        data=csv,
                        file_name=f'Bang_Xep_Hang_Thi_Dua_{datetime.now().strftime("%Y%m%d")}.csv',
                        mime='text/csv',
                    )
            else:
                st.info("Chưa có dữ liệu điểm thi đua cho các nhóm trong bộ lọc này.")

    elif choice == "🕵️ Theo Dõi Tiến Độ & Lịch Hẹn":
        st.header("🕵️ Giám Sát Hoạt Động Của Sinh Viên")
        if not df_nhom_toan_cuc.empty:
            df_loc, nhom_chon_ten = bo_loc_phan_cap(df_nhom_toan_cuc)
            
            if nhom_chon_ten != "Tất cả" and not df_loc.empty:
                nhom_id = df_loc['ID'].iloc[0]
                
                # Biểu đồ cá nhân
                st.write("---")
                st.subheader("📊 Thống kê mức độ đóng góp cá nhân")
                df_bc = pd.DataFrame(ws_baocao.get_all_records())
                if not df_bc.empty:
                    df_bc_nhom = df_bc[df_bc['NhomID'] == nhom_id]
                    if not df_bc_nhom.empty:
                        df_counts = df_bc_nhom['TenSinhVien'].value_counts().reset_index()
                        df_counts.columns = ['Tên Sinh Viên', 'Số lần báo cáo/trao đổi']
                        fig_dong_gop = px.bar(df_counts, x='Tên Sinh Viên', y='Số lần báo cáo/trao đổi', color='Số lần báo cáo/trao đổi')
                        st.plotly_chart(fig_dong_gop, use_container_width=True)
                        
                        # --- BỔ SUNG: CHAT TRỰC TIẾP CỦA GIÁO VIÊN ---
                        st.write("---")
                        st.subheader("💬 Nhật Ký & Thảo Luận Nhóm (Chat)")
                        
                        with st.form("form_chat_gv", clear_on_submit=True):
                            tin_nhan_gv = st.text_area("Nhắn tin / Yêu cầu công việc trực tiếp cho nhóm:")
                            if st.form_submit_button("Gửi tin nhắn"):
                                if tin_nhan_gv:
                                    ws_baocao.append_row([int(nhom_id), "👩‍🏫 Giảng viên", tin_nhan_gv, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""])
                                    st.success("Đã gửi tin nhắn cho nhóm!")
                                    st.rerun()
                                else:
                                    st.warning("Vui lòng nhập nội dung.")
                        
                        st.write("**Lịch sử trao đổi chi tiết của nhóm:**")
                        for _, row in df_bc_nhom.iloc[::-1].iterrows():
                            if "Giảng viên" in str(row['TenSinhVien']):
                                st.markdown(f"<div style='background-color:#ffe6e6; padding:10px; border-radius:10px; margin-bottom:10px; border-left: 4px solid #f44336;'><small><b>{row['TenSinhVien']}</b> <i>({row['NgayNop']})</i></small><br>{row['NoiDung']}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:10px; margin-bottom:10px; border-left: 4px solid #4CAF50;'><small><b>👤 {row['TenSinhVien']}</b> <i>({row['NgayNop']})</i></small><br>{row['NoiDung']}</div>", unsafe_allow_html=True)
                    else: st.info("Nhóm này chưa có hoạt động trao đổi nào.")
                
                # Đặt lịch hẹn & Giao việc
                st.write("---")
                col_lich, col_task = st.columns(2)
                
                with col_lich:
                    st.subheader("📅 Đặt lịch hẹn")
                    with st.form("form_lich"):
                        ngay = st.date_input("Ngày hẹn:")
                        gio = st.time_input("Giờ hẹn:")
                        dia_diem = st.text_input("Địa điểm / Link Meet:")
                        if st.form_submit_button("Chốt lịch"):
                            ws_lichhen.append_row([int(nhom_id), f"{ngay.strftime('%Y-%m-%d')} {gio.strftime('%H:%M')}", dia_diem, "Đã chốt"])
                            st.success("Đã lên lịch hẹn thành công!")

                with col_task:
                    st.subheader("📋 Giao nhiệm vụ & Deadline")
                    with st.form("form_giao_viec", clear_on_submit=True):
                        noi_dung_task = st.text_input("Nội dung công việc / Yêu cầu:")
                        deadline = st.date_input("Hạn chót (Deadline):")
                        if st.form_submit_button("Giao việc cho nhóm"):
                            if noi_dung_task:
                                ws_nhiemvu.append_row([int(nhom_id), noi_dung_task, deadline.strftime("%Y-%m-%d"), "Chưa xong"])
                                st.success("Đã giao việc thành công!")
                            else:
                                st.warning("Vui lòng nhập nội dung công việc.")
            else:
                st.warning("Vui lòng chọn đích danh 1 'Nhóm' ở bộ lọc phía trên để xem chi tiết nhân sự.")

    elif choice == "🎯 Chấm Điểm & Xuất Báo Cáo":
        st.header("🎯 Chấm Điểm Đồ Án / Tiểu Luận")
        if not df_nhom_toan_cuc.empty:
            df_loc, nhom_chon_ten = bo_loc_phan_cap(df_nhom_toan_cuc)
            
            if nhom_chon_ten != "Tất cả" and not df_loc.empty:
                thong_tin = df_loc.iloc[0]
                nhom_id = thong_tin['ID']
                
                st.write("---")
                col_view, col_grade = st.columns([1.5, 1]) 
                with col_view:
                    st.subheader("📄 Nội dung đồ án (Google Docs)")
                    link_goc = thong_tin.get('LinkDoc', '')
                    if link_goc and "docs.google.com" in str(link_goc):
                        components.html(f'<iframe src="{link_goc}?embedded=true" width="100%" height="600" frameborder="0"></iframe>', height=600)
                    else: st.warning("Chưa có link Docs hợp lệ.")

                with col_grade:
                    st.subheader("📝 Rubric Chấm Điểm")
                    with st.form("form_cham_diem"):
                        diem_tb = st.slider("1. Hình thức & Trình bày", 0.0, 10.0, 7.0, 0.5)
                        diem_sp = st.slider("2. Chất lượng nội dung", 0.0, 10.0, 7.0, 0.5)
                        diem_ph = st.slider("3. Tương tác & Phối hợp", 0.0, 10.0, 7.0, 0.5)
                        nx = st.text_area("Nhận xét của giảng viên:")
                        if st.form_submit_button("Lưu Điểm"):
                            tong = round((diem_tb + diem_sp + diem_ph) / 3, 2)
                            ws_danhgia.append_row([int(nhom_id), float(diem_tb), float(diem_sp), float(diem_ph), float(tong), nx])
                            ws_nhom.update_cell(nhom_id + 2, 10, "Hoàn thành") 
                            st.success(f"Đã lưu điểm! Tổng: {tong}")
                            
                    st.write("---")
                    data_dg = ws_danhgia.get_all_records()
                    if data_dg:
                        df_dg = pd.DataFrame(data_dg)
                        diem_nhom = df_dg[df_dg['NhomID'] == nhom_id]
                        if not diem_nhom.empty:
                            dg_cuoi = diem_nhom.iloc[-1]
                            html_content = f"""
                            <html><head><meta charset="utf-8">
                            <style>body {{ font-family: Arial; padding: 20px; line-height: 1.6; }} table {{ width: 100%; border-collapse: collapse; }} th, td {{ border: 1px solid #aaa; padding: 10px; }} th {{ background-color: #f4f4f4; }}</style>
                            </head><body>
                            <h2 style='text-align: center;'>BIÊN BẢN ĐÁNH GIÁ ĐỒ ÁN / TIỂU LUẬN</h2>
                            <p><strong>Khóa/Lớp:</strong> {thong_tin['Khoa']} - {thong_tin['Lop']}</p>
                            <p><strong>Học phần:</strong> {thong_tin['HocPhan']}</p>
                            <p><strong>Đề tài ({thong_tin['TenNhom']}):</strong> {thong_tin['TenDeTai']}</p>
                            <table>
                                <tr><th>Tiêu chí</th><th>Điểm</th></tr>
                                <tr><td>Hình thức & Trình bày</td><td>{dg_cuoi['DiemTrinhBay']}</td></tr>
                                <tr><td>Chất lượng nội dung</td><td>{dg_cuoi['DiemSanPham']}</td></tr>
                                <tr><td>Tương tác & Phối hợp</td><td>{dg_cuoi['DiemPhoiHop']}</td></tr>
                                <tr><td><strong>TỔNG ĐIỂM (HỆ SỐ 10)</strong></td><td><strong><span style="color:red; font-size:18px;">{dg_cuoi['TongDiem']}</span></strong></td></tr>
                            </table>
                            <p><strong>Nhận xét:</strong> {dg_cuoi['NhanXet']}</p>
                            <br><p style="text-align: right;"><strong>Giảng viên hướng dẫn</strong></p>
                            </body></html>
                            """
                            st.download_button(label="📥 Tải file Báo Cáo PDF/HTML", data=html_content.encode('utf-8'), file_name=f"BaoCao_{thong_tin['Khoa']}_{thong_tin['TenNhom']}.html", mime="text/html")
                            if thong_tin.get('EmailNhom', ''):
                                if st.button("📧 Gửi Email Biên Bản Cho Nhóm"):
                                    with st.spinner("Đang gửi email..."):
                                        if send_email_report(thong_tin['EmailNhom'], thong_tin['TenDeTai'], html_content):
                                            st.success("Gửi email thành công!")
                                        else: st.error("Lỗi gửi mail. Cần kiểm tra mật khẩu ứng dụng.")
            else:
                st.warning("Vui lòng lọc đến cấp 'Nhóm' để chấm điểm.")
    
    elif choice == "📊 Tiêu Chí Chấm Điểm":
        st.header("📊 Tiêu Chí Chấm Điểm Đồ Án / Tiểu Luận")
        st.info("💡 Sinh viên vui lòng đọc kỹ các tiêu chí dưới đây để tối ưu hóa điểm số cho bài làm của nhóm mình.")
        
        st.markdown("""
        | Tiêu chí đánh giá | Trọng số | Xuất sắc (8.5 - 10) | Khá (7.0 - 8.4) | Trung bình (5.0 - 6.9) | Yếu (Dưới 5.0) |
        | :--- | :---: | :--- | :--- | :--- | :--- |
        | **1. Cấu trúc & Hình thức** | **15%** | Trình bày chuyên nghiệp, chuẩn học thuật. Văn phong mạch lạc, không lỗi chính tả. Trích dẫn nguồn chuẩn xác. | Trình bày rõ ràng, đúng form. Còn vài lỗi nhỏ đánh máy. Trích dẫn đầy đủ nhưng đôi chỗ chưa chuẩn form. | Bố cục thiếu cân đối. Có khá nhiều lỗi chính tả/ngữ pháp. Trích dẫn sơ sài, thiếu nguồn rõ ràng. | Không tuân thủ cấu trúc. Lỗi chính tả/ngữ pháp chằng chịt. Không có trích dẫn hoặc đạo văn. |
        | **2. Nội dung & Độ sâu** | **35%** | Hiểu cực kỳ sâu sắc vấn đề. Lập luận sắc bén, logic. Dữ liệu phong phú, đáng tin cậy. Có đóng góp mới. | Nắm vững vấn đề trọng tâm. Lập luận tốt nhưng chưa đào sâu. Dữ liệu đầy đủ nhưng thiếu đột phá. | Chỉ nêu bề mặt vấn đề. Lập luận thiếu liên kết. Dữ liệu cũ hoặc chưa sát đề tài. | Đi lạc đề hoặc sai kiến thức cơ bản. Không có dẫn chứng thực tế. |
        | **3. Giải quyết vấn đề** | **20%** | Đề xuất giải pháp thực tiễn, khả thi. Đánh giá được ưu/nhược điểm. Nhìn nhận vấn đề đa chiều. | Có giải pháp rõ ràng, giải quyết được vấn đề. Tính khả thi hoặc tính mới chưa cao. | Giải pháp hời hợt, lý thuyết suông, khó áp dụng vào thực tế. | Không có giải pháp hoặc phi logic, sao chép máy móc. |
        | **4. Thuyết trình/Phản biện** | **15%** | Tự tin, lôi cuốn. Slide trực quan. Trả lời phản biện sắc sảo, đi thẳng trọng tâm. | Thuyết trình lưu loát. Slide gọn gàng. Trả lời được hầu hết các câu hỏi phản biện. | Phụ thuộc tài liệu, đọc slide. Slide rối mắt. Trả lời ấp úng, lan man. | Không nắm được nội dung. Slide cẩu thả. Không trả lời được câu hỏi. |
        | **5. Làm việc nhóm** | **15%** | Cập nhật tiến độ đúng hạn. Phân công rõ ràng, mọi thành viên đều hiểu rõ phần việc. | Nộp bài đúng hạn. Phối hợp tốt nhưng vài cá nhân chưa rành việc của người khác. | Nộp báo cáo trễ hạn. Phân chia không đều, có hiện tượng "gánh team". | Trễ hạn nhiều lần. Nhóm rời rạc, mâu thuẫn hoặc có người không tham gia. |
        """)

    elif choice == "📬 Hòm Thư & Đánh Giá":
        st.header("📬 Hòm Thư Hỗ Trợ & Phân Tích Đánh Giá Chéo")
        
        tab1, tab2, tab3 = st.tabs(["🆘 Giải đáp (SOS)", "🤝 Đánh giá chéo", "⏰ Kiểm soát tiến độ"])
        
        with tab1:
            st.subheader("Quản lý câu hỏi từ Sinh viên")
            df_hd = pd.DataFrame(ws_hoidap.get_all_records())
            
            if not df_hd.empty:
                df_hd_chua_tl = df_hd[df_hd['TrangThai'] == "Chưa trả lời"]
                df_hd_da_tl = df_hd[df_hd['TrangThai'] != "Chưa trả lời"]
                
                if not df_hd_chua_tl.empty:
                    st.warning(f"🔔 Có {len(df_hd_chua_tl)} câu hỏi đang chờ bạn phản hồi!")
                    for idx, row in df_hd_chua_tl.iterrows():
                        with st.expander(f"🔴 {row['TenSinhVien']} (Nhóm ID: {row['NhomID']}) - {row['ThoiGian']}"):
                            st.write(f"**Nội dung hỏi:** {row['CauHoi']}")
                            
                            with st.form(key=f"reply_form_{idx}"):
                                tra_loi = st.text_area("Nhập câu trả lời của bạn:")
                                if st.form_submit_button("Gửi câu trả lời"):
                                    if tra_loi:
                                        ws_hoidap.update_cell(idx + 2, 5, f"👨‍🏫 Giảng viên: {tra_loi}")
                                        st.success("Đã gửi phản hồi thành công!")
                                        st.rerun()
                                    else:
                                        st.error("Vui lòng nhập nội dung trả lời.")
                
                if not df_hd_da_tl.empty:
                    st.write("---")
                    st.write("**Lịch sử các câu hỏi đã giải quyết:**")
                    for idx, row in df_hd_da_tl.iterrows():
                        with st.expander(f"🟢 {row['TenSinhVien']} (Nhóm ID: {row['NhomID']}) - {row['ThoiGian']}"):
                            st.write(f"**Hỏi:** {row['CauHoi']}")
                            st.info(f"**Phản hồi:** {row['TrangThai']}")
            else:
                st.info("Hiện tại không có câu hỏi nào từ sinh viên.")

        with tab2:
            st.subheader("Kết quả Đánh giá chéo từ Sinh viên")
            st.write("Bảng dữ liệu bí mật này giúp bạn nắm được ai là người đóng góp nhiều nhất trong các nhóm.")
            
            df_peer = pd.DataFrame(ws_peer.get_all_records())
            if not df_peer.empty:
                if not df_nhom_toan_cuc.empty:
                    df_hien_thi_peer = df_peer.merge(df_nhom_toan_cuc[['ID', 'TenNhom', 'Khoa', 'Lop']], left_on='NhomID', right_on='ID', how='left')
                    
                    lop_loc = st.selectbox("Lọc kết quả đánh giá theo Lớp:", ["Tất cả"] + df_hien_thi_peer['Lop'].dropna().unique().tolist())
                    if lop_loc != "Tất cả":
                        df_hien_thi_peer = df_hien_thi_peer[df_hien_thi_peer['Lop'] == lop_loc]
                        
                    st.dataframe(df_hien_thi_peer[['Khoa', 'Lop', 'TenNhom', 'NguoiDanhGia', 'NguoiDuocDanhGia', 'Diem', 'NhanXet']], use_container_width=True)
                else:
                    st.dataframe(df_peer, use_container_width=True)
            else:
                st.info("Chưa có sinh viên nào thực hiện đánh giá chéo.")
        
        with tab3:
            st.subheader("⏰ Cảnh Báo Hạn Chót (Trong 24h tới)")
            
            # 1. Chuẩn bị dữ liệu
            df_nv_all = pd.DataFrame(ws_nhiemvu.get_all_records())
            df_nhom_all = pd.DataFrame(ws_nhom.get_all_records())
            
            if not df_nv_all.empty:
                # Chuyển cột Deadline sang định dạng datetime để tính toán
                df_nv_all['Deadline'] = pd.to_datetime(df_nv_all['Deadline'])
                bay_gio = datetime.now()
                han_chot_24h = bay_gio + pd.Timedelta(hours=24)
                
                # Lọc các nhiệm vụ: Chưa xong VÀ Hạn chót <= 24h tới
                df_sap_den_han = df_nv_all[
                    (df_nv_all['TrangThai'] == "Chưa xong") & 
                    (df_nv_all['Deadline'] <= han_chot_24h)
                ]
                
                if not df_sap_den_han.empty:
                    # Kết nối với thông tin nhóm để lấy Email và Tên nhóm
                    df_canh_bao = df_sap_den_han.merge(df_nhom_all[['ID', 'TenNhom', 'EmailNhom', 'TenDeTai']], left_on='NhomID', right_on='ID')
                    
                    st.warning(f"Phát hiện {len(df_canh_bao)} nhiệm vụ sắp đến hạn hoặc đã quá hạn!")
                    st.dataframe(df_canh_bao[['TenNhom', 'NoiDungTask', 'Deadline', 'EmailNhom']], use_container_width=True)
                    
                    # Nút gửi email nhắc nhở đồng loạt
                    if st.button("📧 Gửi Email nhắc nhở đồng loạt cho các nhóm này"):
                        danh_sach_email = df_canh_bao['EmailNhom'].unique()
                        count_success = 0
                        
                        with st.spinner("Đang gửi email nhắc nhở..."):
                            for email_nhom in danh_sach_email:
                                tasks_nhom = df_canh_bao[df_canh_bao['EmailNhom'] == email_nhom]
                                ten_nhom_gui = tasks_nhom['TenNhom'].iloc[0]
                                de_tai_gui = tasks_nhom['TenDeTai'].iloc[0]
                                
                                noi_dung_nhac = f"Chào nhóm {ten_nhom_gui},\n\nGiảng viên nhắc nhở các em có nhiệm vụ sắp đến hạn:\n"
                                for _, r in tasks_nhom.iterrows():
                                    noi_dung_nhac += f"- {r['NoiDungTask']} (Hạn: {r['Deadline'].strftime('%d/%m/%Y')})\n"
                                noi_dung_nhac += "\nCác em khẩn trương hoàn thành đúng hạn nhé.\nTrân trọng."
                                
                                # Gửi email
                                if send_email_report(email_nhom, f"NHẮC HẠN: {de_tai_gui}", noi_dung_nhac):
                                    count_success += 1
                        
                        st.success(f"Đã gửi thành công email nhắc nhở đến {count_success} nhóm!")
                else:
                    st.info("Hiện tại không có nhiệm vụ nào sắp đến hạn trong 24h tới.")
            else:
                st.info("Chưa có dữ liệu nhiệm vụ.")        

# ==========================================
# 5. GIAO DIỆN SINH VIÊN
# ==========================================
elif role == "Sinh viên":
    df_sv_xem = df_nhom_toan_cuc[df_nhom_toan_cuc['MaTruyCap'].astype(str) == user_code]
    
    if not df_sv_xem.empty:
        thong_tin_sv = df_sv_xem.iloc[0]
        nhom_id_ht = thong_tin_sv['ID']
        
        if choice == "💻 Không Gian Làm Việc Chung":
            st.success(f"📌 Đang làm việc: **{thong_tin_sv['Khoa']} | {thong_tin_sv['Lop']} | {thong_tin_sv['HocPhan']} | {thong_tin_sv['TenNhom']}** \n\n 📝 Đề tài: **{thong_tin_sv['TenDeTai']}**")
            
            df_tb = pd.DataFrame(ws_thongbao.get_all_records())
            if not df_tb.empty:
                df_hien_thi = df_tb[df_tb['TrangThai'] == "Hiển thị"]
                if not df_hien_thi.empty:
                    st.write("---")
                    st.subheader("📢 Bảng Tin & Thông Báo Quan Trọng")
                    for _, row in df_hien_thi.iloc[::-1].iterrows():
                        if row['PhanLoai'] == "Khẩn cấp":
                            st.error(f"🚨 **{row['TieuDe']}** ({row['ThoiGian']})\n\n{row['NoiDung']}")
                        elif row['PhanLoai'] == "Hoạt động Đoàn Hội":
                            st.info(f"🌿 **{row['TieuDe']}** ({row['ThoiGian']})\n\n{row['NoiDung']}")
                        else:
                            st.warning(f"📌 **{row['TieuDe']}** ({row['ThoiGian']})\n\n{row['NoiDung']}")
            st.write("---")
            import streamlit as st
 

            df_nv = pd.DataFrame(ws_nhiemvu.get_all_records())
            if not df_nv.empty:
                df_nv_nhom = df_nv[df_nv['NhomID'] == nhom_id_ht]
                if not df_nv_nhom.empty:
                    for idx, row in df_nv_nhom.iterrows():
                        c1, c2 = st.columns([5, 1])
                        with c1:
                            if row['TrangThai'] == "Đã xong":
                                st.markdown(f"~~**{row['NoiDungTask']}** *(Deadline: {row['Deadline']})*~~")
                            else:
                                st.markdown(f"👉 **{row['NoiDungTask']}** *(Deadline: <span style='color:red;'>{row['Deadline']}</span>)*", unsafe_allow_html=True)
                        with c2:
                            if row['TrangThai'] == "Chưa xong":
                                if st.button("Tick Xong ✔️", key=f"task_done_{idx}"):
                                    ws_nhiemvu.update_cell(idx + 2, 4, "Đã xong")
                                    st.rerun()
                            else:
                                if st.button("↩️ Bỏ tick", key=f"task_undo_{idx}"):
                                    ws_nhiemvu.update_cell(idx + 2, 4, "Chưa xong")
                                    st.rerun()
                else:
                    st.info("Nhóm hiện tại chưa có nhiệm vụ nào được giao.")
            else:
                st.info("Chưa có nhiệm vụ nào trên hệ thống.")
            st.write("---")
            col_chat, col_doc = st.columns([1, 2.5])
            with col_chat:
                st.subheader("💬 Nhật Ký & Thảo Luận")
                with st.form("form_chat", clear_on_submit=True):
                    ten_sv = st.text_input("Tên của bạn (Để tính điểm chuyên cần):")
                    tin_nhan = st.text_area("Cập nhật công việc vừa làm:")
                    if st.form_submit_button("Gửi"):
                        if ten_sv and tin_nhan:
                            ws_baocao.append_row([int(nhom_id_ht), ten_sv, tin_nhan, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""])
                            st.rerun()
                        else: st.warning("Vui lòng nhập đủ Tên và Nội dung.")
                
                st.write("---")
                df_bc = pd.DataFrame(ws_baocao.get_all_records())
                if not df_bc.empty:
                    df_chat = df_bc[df_bc['NhomID'] == nhom_id_ht]
                    # --- BỔ SUNG: HIỂN THỊ CHAT BÊN PHÍA SINH VIÊN ---
                    for _, row in df_chat.iloc[::-1].iterrows():
                        if "Giảng viên" in str(row['TenSinhVien']):
                            st.markdown(f"<div style='background-color:#ffe6e6; padding:10px; border-radius:10px; margin-bottom:10px; border-left: 4px solid #f44336;'><small><b>{row['TenSinhVien']}</b> <i>({row['NgayNop']})</i></small><br>{row['NoiDung']}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:10px; margin-bottom:10px; border-left: 4px solid #4CAF50;'><small><b>👤 {row['TenSinhVien']}</b> <i>({row['NgayNop']})</i></small><br>{row['NoiDung']}</div>", unsafe_allow_html=True)

            with col_doc:
                st.subheader("📝 Soạn Thảo Đồ Án / Tiểu Luận Trực Tiếp")
                link_doc = thong_tin_sv.get('LinkDoc', '')
                if link_doc and "docs.google.com" in str(link_doc):
                    st.link_button("↗️ Mở tài liệu ra Tab lớn để dễ gõ", link_doc)
                    components.html(f'<iframe src="{link_doc}?embedded=true" width="100%" height="700px" frameborder="0"></iframe>', height=700)
                else: st.warning("Giáo viên chưa cung cấp tài liệu soạn thảo chung.")
                
        elif choice == "🔍 Tra cứu Điểm & Phản hồi":
            st.header("🔍 Kết Quả & Phản Hồi Từ Giảng Viên")
            
            st.subheader("📅 Lịch hẹn báo cáo sắp tới")
            df_lich = pd.DataFrame(ws_lichhen.get_all_records())
            if not df_lich.empty:
                lich_nhom = df_lich[df_lich['NhomID'] == nhom_id_ht]
                if not lich_nhom.empty: 
                    st.table(lich_nhom[['ThoiGian', 'DiaDiem', 'TrangThai']])
                else: 
                    st.info("Chưa có lịch hẹn nào.")
            else:
                st.info("Hệ thống chưa có dữ liệu lịch hẹn.")
            
            st.write("---")
            st.subheader("🎯 Bảng điểm tổng kết")
            df_dg = pd.DataFrame(ws_danhgia.get_all_records())
            if not df_dg.empty:
                dg_nhom = df_dg[df_dg['NhomID'] == nhom_id_ht]
                if not dg_nhom.empty:
                    st.success(f"🎉 Nhóm đã hoàn thành! Tổng điểm: **{dg_nhom.iloc[-1]['TongDiem']}** / 10")
                    st.table(dg_nhom.iloc[[-1]][['DiemTrinhBay', 'DiemSanPham', 'DiemPhoiHop', 'NhanXet']])
                else: 
                    st.info("Đề tài đang thực hiện, chưa có điểm tổng kết.")
            else:
                st.info("Hệ thống chưa có dữ liệu điểm.")

        elif choice == "📚 Thư Viện Biểu Mẫu" and role == "Sinh viên":
            st.header("📚 Kho Tài Liệu & Biểu Mẫu Hướng Dẫn")
            st.write("Các em tải các biểu mẫu dưới đây để thực hiện đúng quy định của học phần.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info("📂 **Tài liệu quy định**")
                st.link_button("📜 Quy định định dạng báo cáo (PDF)", "https://link_file_cua_ban.pdf")
                st.link_button("📊 Rubric chấm điểm chi tiết", "https://link_rubric.pdf")
                
            with col2:
                st.success("📝 **File mẫu soạn thảo**")
                st.link_button("📄 Mẫu trang bìa & Mục lục (Word)", "https://link_file_word.docx")
                st.link_button("🎨 Mẫu Slide thuyết trình (PPTX)", "https://link_file_pptx.pptx")
        
        elif choice == "🏆 Bảng Xếp Hạng":
            st.header("🏆 Bảng Xếp Hạng Thi Đua")
            st.write(f"Đang hiển thị bảng xếp hạng năng nổ của lớp: **{thong_tin_sv['Lop']}** - Học phần: **{thong_tin_sv['HocPhan']}**")
            
            st.info("💡 **Cách tính điểm thi đua:** Mỗi tin nhắn báo cáo tiến độ (+2 điểm). Mỗi nhiệm vụ hoàn thành (+10 điểm).")
            
            df_bc = pd.DataFrame(ws_baocao.get_all_records())
            df_nv = pd.DataFrame(ws_nhiemvu.get_all_records())
            
            # Chỉ lấy các nhóm cùng Lớp và cùng Học phần
            df_cung_lop = df_nhom_toan_cuc[
                (df_nhom_toan_cuc['Lop'] == thong_tin_sv['Lop']) & 
                (df_nhom_toan_cuc['HocPhan'] == thong_tin_sv['HocPhan'])
            ]
            
            bang_diem = []
            for _, row_nhom in df_cung_lop.iterrows():
                n_id = row_nhom['ID']
                diem_chat = 0
                diem_task = 0
                
                # Tính điểm Chat (không tính tin nhắn của Giảng viên)
                if not df_bc.empty and 'NhomID' in df_bc.columns:
                    sv_chat = df_bc[(df_bc['NhomID'] == n_id) & (~df_bc['TenSinhVien'].astype(str).str.contains("Giảng viên", na=False))]
                    diem_chat = len(sv_chat) * 2
                
                # Tính điểm Task
                if not df_nv.empty and 'NhomID' in df_nv.columns:
                    diem_task = len(df_nv[(df_nv['NhomID'] == n_id) & (df_nv['TrangThai'] == 'Đã xong')]) * 10
                    
                tong_diem = diem_chat + diem_task
                
                bang_diem.append({
                    "Tên Nhóm": row_nhom['TenNhom'],
                    "Đề Tài": row_nhom['TenDeTai'],
                    "Điểm Trao Đổi": diem_chat,
                    "Điểm Nhiệm Vụ": diem_task,
                    "Điểm Năng Nổ": tong_diem
                })
                
            df_bang_diem = pd.DataFrame(bang_diem).sort_values(by="Điểm Năng Nổ", ascending=False).reset_index(drop=True)
            
            if not df_bang_diem.empty and df_bang_diem['Điểm Năng Nổ'].sum() > 0:
                st.write("---")
                
                # Hiển thị Top 3 có thêm tên Đề tài
                c1, c2, c3 = st.columns(3)
                if len(df_bang_diem) > 0:
                    c1.success(f"""
                        🥇 **Hạng 1: {df_bang_diem.iloc[0]['Tên Nhóm']}**
                        \n 📝 Đề tài: {df_bang_diem.iloc[0]['Đề Tài']}
                        \n 🔥 {df_bang_diem.iloc[0]['Điểm Năng Nổ']} Điểm
                    """)
                if len(df_bang_diem) > 1:
                    c2.info(f"""
                        🥈 **Hạng 2: {df_bang_diem.iloc[1]['Tên Nhóm']}**
                        \n 📝 Đề tài: {df_bang_diem.iloc[1]['Đề Tài']}
                        \n ⚡ {df_bang_diem.iloc[1]['Điểm Năng Nổ']} Điểm
                    """)
                if len(df_bang_diem) > 2:
                    c3.warning(f"""
                        🥉 **Hạng 3: {df_bang_diem.iloc[2]['Tên Nhóm']}**
                        \n 📝 Đề tài: {df_bang_diem.iloc[2]['Đề Tài']}
                        \n 🌟 {df_bang_diem.iloc[2]['Điểm Năng Nổ']} Điểm
                    """)
                
                st.write("---")
                
                # Biểu đồ cập nhật thêm Hover Data (Chi tiết điểm khi rê chuột)
                fig = px.bar(df_bang_diem, x="Tên Nhóm", y="Điểm Năng Nổ", color="Điểm Năng Nổ", text="Điểm Năng Nổ", 
                             title="Biểu đồ năng lượng đóng góp của các nhóm trong lớp", color_continuous_scale="Viridis",
                             hover_data=["Đề Tài", "Điểm Trao Đổi", "Điểm Nhiệm Vụ"])
                st.plotly_chart(fig, use_container_width=True)
                
                # Nút mở rộng xem bảng chi tiết và xuất Excel
                with st.expander("👁️ Xem chi tiết cơ cấu điểm & Tải Bảng Xếp Hạng"):
                    st.dataframe(df_bang_diem[['Tên Nhóm', 'Đề Tài', 'Điểm Trao Đổi', 'Điểm Nhiệm Vụ', 'Điểm Năng Nổ']], use_container_width=True)
                    csv_sv = df_bang_diem.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Tải Bảng Điểm Thi Đua (CSV)",
                        data=csv_sv,
                        file_name=f'Bang_Xep_Hang_Lop_{thong_tin_sv["Lop"]}_{datetime.now().strftime("%Y%m%d")}.csv',
                        mime='text/csv',
                    )
                
            else:
                st.info("Chưa có điểm thi đua nào được ghi nhận. Các nhóm hãy nhắn tin trao đổi và hoàn thành nhiệm vụ để khai trương bảng xếp hạng nhé!")

        elif choice == "🤝 Đánh Giá Chéo" and role == "Sinh viên":
            st.header("🤝 Đánh Giá Đóng Góp Nội Bộ Nhóm")
            st.warning("Lưu ý: Kết quả đánh giá này sẽ được gửi bí mật đến Giảng viên để làm căn cứ chấm điểm cá nhân cuối kỳ.")
            
            with st.form("form_peer_review", clear_on_submit=True):
                ten_nguoi_nhan_xet = st.text_input("Tên của bạn:")
                ten_nguoi_duoc_nhan_xet = st.text_input("Tên bạn cùng nhóm muốn đánh giá:")
                
                muc_do = st.select_slider(
                    "Mức độ đóng góp của bạn này vào công việc chung:",
                    options=["Rất kém", "Kém", "Trung bình", "Tốt", "Rất xuất sắc"]
                )
                diem_so = {"Rất kém": 2, "Kém": 4, "Trung bình": 6, "Tốt": 8, "Rất xuất sắc": 10}[muc_do]
                
                nhan_xet_chi_tiet = st.text_area("Lý do đánh giá hoặc mô tả đóng góp của bạn này:")
                
                if st.form_submit_button("Gửi đánh giá bí mật"):
                    if ten_nguoi_nhan_xet and ten_nguoi_duoc_nhan_xet:
                        ws_peer.append_row([int(nhom_id_ht), ten_nguoi_nhan_xet, ten_nguoi_duoc_nhan_xet, diem_so, nhan_xet_chi_tiet])
                        st.success("Cảm ơn em! Thông tin đã được ghi nhận bí mật.")
                    else: st.error("Vui lòng điền đầy đủ tên.")
        
        elif choice == "🆘 Gửi Câu Hỏi Cho GV":
            st.header("🆘 Kênh Hỗ Trợ Khẩn Cấp / Hỏi Đáp Riêng")
            st.write("Kênh này được bảo mật tuyệt đối. Các thành viên khác trong nhóm sẽ không thể xem được nội dung em trao đổi với Giảng viên.")
            
            with st.form("form_sos"):
                ten_sv_hoi = st.text_input("Nhập Họ Tên hoặc MSSV của em (Dùng làm chìa khóa bảo mật):")
                noi_dung_hoi = st.text_area("Nội dung câu hỏi hoặc vấn đề cần hỗ trợ:")
                is_urgent = st.checkbox("Vấn đề khẩn cấp cần phản hồi ngay?")
                
                if st.form_submit_button("Gửi câu hỏi"):
                    if ten_sv_hoi and noi_dung_hoi:
                        tag = "[KHẨN CẤP]" if is_urgent else "[Bình thường]"
                        ws_hoidap.append_row([int(nhom_id_ht), ten_sv_hoi.strip(), f"{tag} {noi_dung_hoi}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Chưa trả lời"])
                        st.success("Câu hỏi đã được gửi bí mật đến Giảng viên!")
                    else: st.warning("Vui lòng nhập đủ thông tin.")

            st.write("---")
            
            st.subheader("📬 Hòm Thư Phản Hồi Cá Nhân")
            st.info("🔐 Nhập đúng Họ Tên/MSSV em đã dùng để gửi câu hỏi để xem Giảng viên trả lời (Bảo mật 1-1).")
            
            chia_khoa = st.text_input("Nhập Họ Tên/MSSV để mở khóa hòm thư:")
            
            if chia_khoa:
                df_hd_sv = pd.DataFrame(ws_hoidap.get_all_records())
                if not df_hd_sv.empty:
                    df_hd_nhom = df_hd_sv[df_hd_sv['NhomID'] == nhom_id_ht]
                    
                    if not df_hd_nhom.empty:
                        df_ca_nhan = df_hd_nhom[df_hd_nhom['TenSinhVien'].astype(str).str.lower() == chia_khoa.strip().lower()]
                        
                        if not df_ca_nhan.empty:
                            st.success(f"🔓 Đã mở khóa hòm thư của: **{chia_khoa}**")
                            for idx, row in df_ca_nhan.iloc[::-1].iterrows(): 
                                with st.container():
                                    st.markdown(f"**Em hỏi:** {row['CauHoi']} *(Lúc: {row['ThoiGian']})*")
                                    if row['TrangThai'] == "Chưa trả lời":
                                        st.warning("⏳ Giảng viên đang xem xét và sẽ trả lời sớm...")
                                    else:
                                        st.success(f"✔️ {row['TrangThai']}")
                                    st.write("---")
                        else:
                            st.error("Không tìm thấy câu hỏi nào khớp với Họ Tên/MSSV này. Vui lòng nhập chính xác chữ em đã dùng để gửi.")
                else:
                    st.info("Hệ thống chưa có dữ liệu hỏi đáp.")
            
            st.subheader("📅 Lịch hẹn báo cáo sắp tới")
            df_lich = pd.DataFrame(ws_lichhen.get_all_records())
            if not df_lich.empty:
                lich_nhom = df_lich[df_lich['NhomID'] == nhom_id_ht]
                if not lich_nhom.empty: st.table(lich_nhom[['ThoiGian', 'DiaDiem', 'TrangThai']])
                else: st.info("Chưa có lịch hẹn nào.")
            
            st.write("---")
            st.subheader("🎯 Bảng điểm tổng kết")
            df_dg = pd.DataFrame(ws_danhgia.get_all_records())
            if not df_dg.empty:
                dg_nhom = df_dg[df_dg['NhomID'] == nhom_id_ht]
                if not dg_nhom.empty:
                    st.success(f"🎉 Nhóm đã hoàn thành! Tổng điểm: **{dg_nhom.iloc[-1]['TongDiem']}** / 10")
                    st.table(dg_nhom.iloc[[-1]][['DiemTrinhBay', 'DiemSanPham', 'DiemPhoiHop', 'NhanXet']])
                else: st.info("Đề tài đang thực hiện, chưa có điểm tổng kết.")
    else: st.error("Mã truy cập bị lỗi. Vui lòng liên hệ Giảng viên.")
