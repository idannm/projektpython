import streamlit as st
import subprocess
import os

# הגדרת כותרת ועיצוב בסיסי
st.set_page_config(page_title="Platform CLI", layout="wide")
st.title("☁️ Platform Engineering CLI Manager")

# תפריט צד לבחירת השירות
resource = st.sidebar.selectbox("Select AWS Resource", ["EC2", "S3", "Route53"])

def run_cli_command(command_list):
    """
    פונקציית עזר להרצת פקודות ה-CLI
    """
    try:
        with st.spinner('Executing command...'):
            result = subprocess.run(
                command_list,
                capture_output=True,
                text=True
            )
        
        # אם הפקודה הצליחה (Return Code 0)
        if result.returncode == 0:
            st.success("✅ Success!")
            # מציג את הפלט בתוך קופסה מסודרת
            st.code(result.stdout, language="bash")
        else:
            # אם הייתה שגיאה
            st.error("❌ Error occurred")
            st.code(result.stderr + "\n" + result.stdout, language="bash")
            
    except Exception as e:
        st.error(f"Execution Error: {str(e)}")

# ==================== EC2 Section ====================
if resource == "EC2":
    st.header("💻 EC2 Instance Management")
    action = st.selectbox("Choose Action", ["Create Instance", "List Instances", "Start Instance", "Stop Instance"])

    if action == "Create Instance":
        st.subheader("Launch New Instance")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Instance Name (Tag)")
        with col2:
            type_ = st.selectbox("Instance Type", ["t3.micro", "t2.small"])
        
        if st.button("🚀 Create EC2"):
            if name:
                run_cli_command(["python", "main.py", "ec2", "create", "--name", name, "--type", type_])
            else:
                st.warning("Please enter a name for the instance.")

    elif action == "List Instances":
        st.subheader("View My Instances")
        if st.button("📋 Refresh List"):
            run_cli_command(["python", "main.py", "ec2", "list"])

    elif action in ["Start Instance", "Stop Instance"]:
        st.subheader(f"{action.split()[0]} Instance")
        instance_id = st.text_input("Enter Instance ID (from List)")
        
        # מפענח אם הפעולה היא start או stop
        cmd_action = "start" if "Start" in action else "stop"
        
        if st.button(f"⚡ {action}"):
            if instance_id:
                run_cli_command(["python", "main.py", "ec2", cmd_action, instance_id])
            else:
                st.warning("Please enter an Instance ID.")

# ==================== S3 Section ====================
elif resource == "S3":
    st.header("🪣 S3 Storage Management")
    action = st.selectbox("Choose Action", ["Create Bucket", "List Buckets", "Upload File"])

    if action == "Create Bucket":
        st.subheader("Create New Bucket")
        bucket_name = st.text_input("Bucket Name (Must be unique globally!)")
        is_public = st.checkbox("Make Public? (Warning: Allows world read access)")
        
        if st.button("✨ Create Bucket"):
            if bucket_name:
                cmd = ["python", "main.py", "s3", "create", "--name", bucket_name]
                if is_public:
                    cmd.append("--public")
                    # מוסיף דגל yes כדי לדלג על השאלה האינטראקטיבית שנתקעת ב-UI
                    cmd.append("--yes")
                run_cli_command(cmd)
            else:
                st.warning("Please enter a bucket name.")

    elif action == "List Buckets":
        st.subheader("View My Buckets")
        if st.button("📋 Refresh Bucket List"):
            run_cli_command(["python", "main.py", "s3", "list"])

    elif action == "Upload File":
        st.subheader("Upload File to Bucket")
        
        # שלב 1: בחירת באקט
        target_bucket = st.text_input("Target Bucket Name")
        
        # שלב 2: בחירת קובץ מהמחשב
        uploaded_file = st.file_uploader("Choose a file to upload")
        
        if st.button("⬆️ Upload Now"):
            if target_bucket and uploaded_file is not None:
                # טריק: שומרים את הקובץ זמנית בדיסק כדי שה-CLI יוכל לקרוא אותו
                temp_filename = uploaded_file.name
                with open(temp_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # מריצים את פקודת ה-CLI
                run_cli_command(["python", "main.py", "s3", "upload", "--bucket", target_bucket, "--file", temp_filename])
                
                # מוחקים את הקובץ הזמני
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
            else:
                st.warning("Please provide both a bucket name and a file.")

# ==================== Route53 Section ====================
elif resource == "Route53":
    st.header("🌐 Route53 DNS Management")
    action = st.selectbox("Choose Action", ["Create Hosted Zone", "List Zones", "Create DNS Record"])

    if action == "Create Hosted Zone":
        st.subheader("Create New DNS Zone")
        domain_name = st.text_input("Domain Name (e.g., myapp.internal)")
        
        if st.button("🌐 Create Zone"):
            if domain_name:
                run_cli_command(["python", "main.py", "r53", "create", "--name", domain_name])
            else:
                st.warning("Please enter a domain name.")

    elif action == "List Zones":
        st.subheader("View Managed Zones")
        if st.button("📋 Refresh Zones List"):
            run_cli_command(["python", "main.py", "r53", "list"])

    elif action == "Create DNS Record":
        st.subheader("Add Record to Zone")
        
        col1, col2 = st.columns(2)
        with col1:
            zone_id = st.text_input("Hosted Zone ID (Copy from List)")
            record_name = st.text_input("Record Name (e.g., www.myapp.internal)")
        with col2:
            record_type = st.selectbox("Record Type", ["A", "CNAME", "TXT"])
            record_value = st.text_input("Value (e.g., 192.168.1.1)")

        if st.button("➕ Add Record"):
            if zone_id and record_name and record_value:
                # שימוש בפקודה create_record (עם קו תחתון כפי שהגדרנו ב-main.py)
                run_cli_command([
                    "python", "main.py", "r53", "create_record",
                    "--zone-id", zone_id,
                    "--name", record_name,
                    "--type", record_type,
                    "--value", record_value
                ])
            else:
                st.warning("Please fill in all fields (Zone ID, Name, Value).")

# Footer
st.markdown("---")
st.caption("Platform Engineering Final Project | Built with Python, Boto3 & Streamlit")
