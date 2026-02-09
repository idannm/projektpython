import boto3
import click
import os
import botocore
import time
import re

# קביעת שם משתמש לטובת תיוג (לפי הדרישות)
USERNAME = os.environ.get('USER', 'user')

# === Clients ===
# יצירת חיבורים לשירותי AWS
ec2_client = boto3.client('ec2')
s3_client = boto3.client('s3')
r53_client = boto3.client('route53')

@click.group()
def cli():
    """Platform Engineering CLI Tool - Final Project"""
    pass

# ==========================================
#                  EC2
# ==========================================
@cli.group()
def ec2():
    """Manage EC2 Resources"""
    pass

@ec2.command()
@click.option('--name', required=True, help="Name tag for the instance")
@click.option('--type', type=click.Choice(['t3.micro','t2.small']), required=True, help="Instance type (limited)")
def create(name, type):
    """Create a new EC2 instance with limits."""
    try:
        # 1. בדיקת מכסה (Hard Cap): מקסימום 2 שרתים רצים
        instances = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:CreatedBy', 'Values': ['platform-cli']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        running_count = sum(len(r['Instances']) for r in instances['Reservations'])
        
        if running_count >= 2:
            click.echo('Error: Hard cap of 2 running instances reached. Cannot create more.')
            return

        # 2. מציאת AMI עדכני של Ubuntu
        amis = ec2_client.describe_images(
            Filters=[{'Name':'name','Values':['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']}], 
            Owners=['099720109477']
        )
        # מיון לפי תאריך כדי לקחת את הכי חדש
        latest_image = sorted(amis['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]['ImageId']

        # 3. יצירת השרת עם תגיות
        ec2_client.run_instances(
            ImageId=latest_image, 
            InstanceType=type, 
            MinCount=1, 
            MaxCount=1, 
            TagSpecifications=[{
                'ResourceType':'instance',
                'Tags':[
                    {'Key':'Name','Value':name},
                    {'Key':'CreatedBy','Value':'platform-cli'},
                    {'Key':'Owner','Value':USERNAME},
                    {'Key':'Project','Value':'FinalProject'}
                ]
            }]
        )
        click.echo(f'Success: Instance {name} created successfully.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
def list():
    """List only instances created by this CLI."""
    try:
        instances = ec2_client.describe_instances(Filters=[{'Name':'tag:CreatedBy','Values':['platform-cli']}])
        click.echo(f"{'ID':<20} {'Name':<20} {'State':<10} {'Type':<10}")
        click.echo("-" * 65)
        for r in instances['Reservations']:
            for i in r['Instances']:
                name = next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='Name'), 'N/A')
                click.echo(f'{i["InstanceId"]:<20} {name:<20} {i["State"]["Name"]:<10} {i["InstanceType"]:<10}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def start(instance_id):
    """Start an EC2 instance."""
    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        click.echo(f'Success: Instance {instance_id} started.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def stop(instance_id):
    """Stop an EC2 instance."""
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        click.echo(f'Success: Instance {instance_id} stopped.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ==========================================
#                  S3
# ==========================================
@cli.group()
def s3():
    """Manage S3 Buckets"""
    pass

@s3.command()
@click.option('--name', required=True, help="Bucket name")
@click.option('--public', is_flag=True, help="Make bucket public")
@click.option('--yes', is_flag=True, help="Skip confirmation prompt (for UI)")
def create(name, public, yes):
    """Create an S3 bucket with tagging and region support."""
    try:
        # 1. תיקון שם הבאקט (Sanitization) - אותיות קטנות ומקפים בלבד
        original_name = name
        name = name.lower().replace('_', '-').strip()
        
        if original_name != name:
            click.echo(f"Warning: Bucket name sanitized from '{original_name}' to '{name}' to meet AWS rules.")

        # בדיקת תקינות סופית לשם
        if not re.match(r'^[a-z0-9.-]+$', name):
            click.echo("Error: Bucket name contains invalid characters. Use only lowercase letters, numbers, and hyphens.")
            return

        # 2. אישור אבטחה אם הבאקט ציבורי
        if public and not yes:
            confirm = click.prompt('WARNING: Are you sure you want a public bucket? (yes/no)')
            if confirm.lower() != 'yes':
                click.echo('Bucket creation cancelled.')
                return

        # 3. זיהוי האזור (Region) הנוכחי כדי למנוע קריסות
        session = boto3.session.Session()
        current_region = session.region_name
        
        # ברירת מחדל אם לא מוגדר
        if current_region is None:
            current_region = 'us-east-1'

        # יצירת הבאקט (תחביר שונה ל-us-east-1 ולשאר העולם)
        if current_region == 'us-east-1':
            s3_client.create_bucket(Bucket=name)
        else:
            s3_client.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={'LocationConstraint': current_region}
            )

        # 4. הוספת תגיות (חובה לפי התרגיל כדי לזהות שזה שלנו)
        s3_client.put_bucket_tagging(
            Bucket=name,
            Tagging={
                'TagSet': [
                    {'Key': 'CreatedBy', 'Value': 'platform-cli'},
                    {'Key': 'Owner', 'Value': USERNAME},
                    {'Key': 'Access', 'Value': 'Public' if public else 'Private'}
                ]
            }
        )
        
        # 5. הסרת חסימת גישה ציבורית (רק אם המשתמש ביקש)
        if public:
            s3_client.delete_public_access_block(Bucket=name)
            
        click.echo(f'Success: Bucket {name} created in {current_region}.')

    except Exception as e:
        # תופס שגיאה אם השם תפוס
        if 'BucketAlreadyExists' in str(e) or 'BucketAlreadyOwnedByYou' in str(e):
             click.echo("Error: Bucket name is already taken globally. Please choose a different name.")
        else:
             click.echo(f"Error: {str(e)}")

@s3.command()
def list():
    """List only buckets created by this CLI."""
    try:
        # S3 לא תומך בסינון מובנה ברשימה, צריך לעבור אחד אחד
        all_buckets = s3_client.list_buckets().get('Buckets', [])
        found_any = False
        
        click.echo(f"{'Bucket Name':<40} {'Creation Date'}")
        click.echo("-" * 65)
        
        for b in all_buckets:
            try:
                # הבאת תגיות לכל באקט
                tags = s3_client.get_bucket_tagging(Bucket=b['Name'])
                tag_set = tags.get('TagSet', [])
                
                # בדיקה אם התגית CreatedBy=platform-cli קיימת
                if any(t['Key'] == 'CreatedBy' and t['Value'] == 'platform-cli' for t in tag_set):
                    click.echo(f"{b['Name']:<40} {b['CreationDate']}")
                    found_any = True
            except botocore.exceptions.ClientError:
                # דילוג על באקטים שאין להם תגיות או שאין לנו גישה אליהם
                continue
        
        if not found_any:
            click.echo("No CLI-created buckets found.")

    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
@click.option('--bucket', required=True)
@click.option('--file', required=True)
def upload(bucket, file):
    """Upload a file to a CLI-created bucket."""
    try:
        # 1. בדיקה שהקובץ קיים בדיסק
        if not os.path.exists(file):
             click.echo(f"Error: Local file '{file}' not found.")
             return

        # 2. בדיקה שהבאקט נוצר על ידי המערכת (לפי תגיות)
        try:
            tags = s3_client.get_bucket_tagging(Bucket=bucket)
            tag_set = tags.get('TagSet', [])
            if not any(t['Key'] == 'CreatedBy' and t['Value'] == 'platform-cli' for t in tag_set):
                 click.echo("Error: You can only upload to buckets created by this CLI tool.")
                 return
        except botocore.exceptions.ClientError:
             click.echo("Error: Bucket tags not found or bucket does not exist.")
             return

        # 3. העלאת הקובץ
        file_name = os.path.basename(file)
        s3_client.upload_file(file, bucket, file_name)
        click.echo(f'Success: File {file_name} uploaded to {bucket}.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ==========================================
#                  Route53
# ==========================================
@cli.group()
def r53():
    """Manage Route53 DNS"""
    pass

@r53.command()
@click.option('--name', required=True)
def create(name):
    """Create a new Hosted Zone."""
    try:
        # הוספת זמן לשם הייחודי כדי למנוע התנגשויות
        ref = f"{name}-{time.time()}" 
        resp = r53_client.create_hosted_zone(
            Name=name, 
            CallerReference=ref, 
            HostedZoneConfig={'Comment':'Created by platform-cli'}
        )
        click.echo(f'Success: Zone {name} created, ID: {resp["HostedZone"]["Id"]}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command()
def list():
    """List Hosted Zones created by this CLI."""
    try:
        zones = r53_client.list_hosted_zones()['HostedZones']
        click.echo(f"{'Zone Name':<30} {'ID'}")
        click.echo("-" * 50)
        found = False
        for z in zones:
            # בדיקה לפי הערה (Comment) כי תגיות ב-Route53 זה מורכב יותר
            if 'Comment' in z.get('Config', {}) and 'platform-cli' in z['Config']['Comment']:
                click.echo(f'{z["Name"]:<30} {z["Id"]}')
                found = True
        
        if not found:
            click.echo("No CLI-created zones found.")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command(name='create_record')
@click.option('--zone-id', required=True)
@click.option('--name', required=True)
@click.option('--type', required=True, type=click.Choice(['A', 'CNAME', 'TXT']))
@click.option('--value', required=True)
def create_record(zone_id, name, type, value):
    """Create a DNS record in a hosted zone."""
    try:
        r53_client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Changes':[{
                    'Action':'UPSERT',
                    'ResourceRecordSet':{
                        'Name':name,
                        'Type':type,
                        'TTL':300,
                        'ResourceRecords':[{'Value':value}]
                    }
                }]
            }
        )
        click.echo(f'Success: Record {name} -> {value} created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

if __name__=='__main__':
    cli()
