# פרויקט מסכם - Platform Engineering
**מגיש:** עידן

## אודות הפרויקט
כלי לניהול משאבי AWS המאפשר למפתחים להקים תשתיות (EC2, S3, Route53) באופן עצמאי.
המערכת כוללת ממשק גרפי (UI) וכלי שורת פקודה (CLI), ואוכפת נהלי אבטחה, מגבלות משאבים (עד 2 שרתים) ותיוג אוטומטי לכל משאב (`CreatedBy=platform-cli`).

## התקנה והרצה
1.  ודאו שמותקן **Python 3.8+** ו-**AWS CLI** מוגדר (`aws configure`).
2.  פתחו טרמינל בתיקיית הפרויקט והתקינו את הספריות:
    ```bash
    pip install -r requirements.txt
    ```
3.  **להפעלת הממשק הגרפי:**
    ```bash
    streamlit run app2.py
    ```

## דוגמאות שימוש (CLI)
ניתן להשתמש בכלי גם דרך הטרמינל:
```bash
# EC2: יצירת שרת (מוגבל ל-t3.micro/t2.small)
python main.py ec2 create --name web-server --type t3.micro

# S3: יצירת באקט והעלאת קובץ
python main.py s3 create --name my-project-files
python main.py s3 upload --bucket my-project-files --file ./data.txt

# Route53: יצירת אזור DNS
python main.py r53 create --name myapp.local
