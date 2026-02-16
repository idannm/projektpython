# פרויקט מסכם - Platform Engineering
**מגיש:** עידן

## 📌 אודות הפרויקט
כלי לניהול משאבי AWS (EC2, S3, Route53) המאפשר למפתחים להקים תשתיות באופן עצמאי (Self-Service).
המערכת כוללת ממשק גרפי (UI) וכלי שורת פקודה (CLI), ואוכפת נהלי אבטחה, מגבלות משאבים (Hard Cap של 2 שרתים) ותיוג אוטומטי לכל משאב (`CreatedBy=platform-cli`).

## ⚙️ דרישות קדם (Prerequisites)
1.  **Python 3.8** ומעלה.
2.  **AWS CLI** מותקן ומוגדר (`aws configure` עם פרטי הגישה).

## 📦 התקנה והרצה
1.  פתחו טרמינל בתיקיית הפרויקט והתקינו את הספריות:
    ```bash
    pip install -r requirements.txt
    ```

2.  **להפעלת הממשק הגרפי (מומלץ):**
    ```bash
    streamlit run app2.py
    ```

## 🚀 דוגמאות שימוש (CLI)
ניתן להשתמש בכלי גם דרך הטרמינל. יש להקפיד להשתמש ב-`python3`.

### 1. ניהול שרתים (EC2)
```bash
# יצירת שרת (מוגבל ל-t3.micro/t2.small)
python3 main.py ec2 create --name web-server --type t3.micro

# הצגת רשימת השרתים שלי (מסונן לפי תגיות)
python3 main.py ec2 list
