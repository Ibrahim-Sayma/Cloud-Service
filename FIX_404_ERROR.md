# 🔴 حل مشكلة 404 على /jobs/submit

## المشكلة من الصورة:
```
POST /jobs/submit HTTP/1.1" 404 Not Found
```

بينما:
```
GET /files/ HTTP/1.1" 200 OK
```

هذا يعني:
- ✅ الـ Backend شغال
- ❌ الـ `/jobs/submit` route غير مسجل أو فيه خطأ

---

## السبب المحتمل #1: Uvicorn Cache

الـ Uvicorn ممكن يكون cached old version من الكود.

### الحل:

#### 1. أوقف الـ server تماماً (Ctrl+C)

#### 2. امسح الـ Python cache:
```bash
cd backend
Remove-Item -Recurse -Force __pycache__
Remove-Item -Recurse -Force routers\__pycache__
Remove-Item -Recurse -Force services\__pycache__
```

#### 3. شغل الـ server من جديد:
```bash
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. تحقق من الـ startup logs:
يجب أن ترى في الـ logs:
```
INFO: 🚀 Cloud Service API started
INFO: 📋 Available routes:
INFO:   POST /jobs/submit
INFO:   GET /jobs/{job_id}
...
```

---

## السبب المحتمل #2: Import Error

قد يكون هناك خطأ في استيراد `SparkManager` أو `file_exists`.

### الحل:

قبل تشغيل الـ server، اختبر الـ imports:
```bash
cd backend
py test_import.py
```

يجب أن ترى:
```
✅ Files router imported successfully
✅ Jobs router imported successfully
   Jobs router paths:
   ['POST'] /submit
   ['GET'] /{job_id}
   ...
```

إذا ظهر خطأ، يعني فيه مشكلة بالـ dependencies.

---

## السبب المحتمل #3: مشكلة في services/storage.py

دعني أتحقق من هذا الملف.

### الحل:

تأكد من وجود `services/storage.py` وأن فيه function `file_exists`:

```python
# services/storage.py
import os

STORAGE_PATH = "../storage"

def file_exists(filename: str) -> bool:
    file_path = os.path.join(STORAGE_PATH, filename)
    return os.path.exists(file_path) and os.path.isfile(file_path)
```

إذا الملف مش موجود، هذا سبب الـ import error.

---

## الحل النهائي (Step by Step):

### 1️⃣ امسح الـ cache:
```powershell
cd "c:\Users\ibrah\OneDrive\Desktop\Cloud Service\backend"
Remove-Item -Recurse -Force __pycache__, routers\__pycache__, services\__pycache__ -ErrorAction SilentlyContinue
```

### 2️⃣ اختبر الـ imports:
```powershell
py test_import.py
```

### 3️⃣ شغل الـ server:
```powershell
py -m uvicorn main:app --reload --port 8000
```

### 4️⃣ راقب الـ startup logs واتأكد من:
- `POST /jobs/submit` موجودة
- `GET /jobs/{job_id}` موجودة

### 5️⃣ اختبر من الـ browser:
افتح: http://localhost:8000/docs

وابحث عن `/jobs/submit` endpoint.

---

## اختبار سريع بـ curl:

```powershell
# Test 1: Root endpoint
curl http://localhost:8000/

# Test 2: Files list
curl http://localhost:8000/files/

# Test 3: Jobs submit (مع dummy data)
curl -X POST http://localhost:8000/jobs/submit -H "Content-Type: application/json" -d '{\"filename\": \"test.csv\", \"job_type\": \"stats\", \"params\": {}}'
```

---

## إذا ما زالت المشكلة موجودة:

أرسل لي:
1. **Startup logs** من الـ Uvicorn
2. صورة من **http://localhost:8000/docs**
3. نتيجة تشغيل `test_import.py`

وبنحلها! 💪
