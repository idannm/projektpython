import streamlit as st
import subprocess

st.title("Platform CLI Manager")

resource = st.selectbox("Resource type", ["EC2", "S3", "Route53"])

if resource == "EC2":
    st.header("EC2 Management")

    action = st.selectbox("Action", ["Create", "List", "Start", "Stop"])
    
    if action == "Create":
        name = st.text_input("Instance Name")
        type_ = st.selectbox("Instance Type", ["t3.micro", "t2.small"])
        if st.button("Create EC2"):
            result = subprocess.run(
                ["python", "main.py", "ec2", "create", "--name", name, "--type", type_],
                capture_output=True, text=True
            )
            st.text(result.stdout)
    
    elif action == "List":
        if st.button("List EC2"):
            result = subprocess.run(["python", "main.py", "ec2", "list"], capture_output=True, text=True)
            st.text(result.stdout)

    elif action in ["Start", "Stop"]:
        instance_id = st.text_input("Instance ID")
        if st.button(f"{action} EC2"):
            result = subprocess.run(
                ["python", "main.py", "ec2", action.lower(), instance_id],
                capture_output=True, text=True
            )
            st.text(result.stdout)
