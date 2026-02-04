# projektpython
📌 EC2 Demo
# Create instance
python main.py ec2 create --name MyServer --type t3.micro

# List instances
python main.py ec2 list

# Stop instance
python main.py ec2 stop i-05d50057c7ebad7c6

# Start instance
python main.py ec2 start i-05d50057c7ebad7c6

📌 S3 Demo
# Create bucket
python main.py s3 create --name idan-demo-bucket --public

# List buckets
python main.py s3 list

# Upload file
python main.py s3 upload --bucket idan-demo-bucket --file test.txt

📌 Route53 Demo
# Create hosted zone
python main.py r53 create --name eexample.com

# List zones
python main.py r53 list
