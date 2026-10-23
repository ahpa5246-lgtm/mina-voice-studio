# تثبيت Mina Voice Studio

المشروع محلي ومفتوح المصدر. الواجهة تعمل بلا مفاتيح API مدفوعة، لكنها لا تولّد صوتًا قبل تثبيت المحركات وأوزان النماذج. أوزان النماذج ليست ضمن هذا المستودع.

## 1. تشغيل الواجهة

يتطلب Python 3.11 (موصى به).

Windows PowerShell:

```powershell
git clone https://github.com/ahpa5246-lgtm/mina-voice-studio.git
cd mina-voice-studio
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
```

افتح http://127.0.0.1:7860

## 2. محرك Chatterbox Multilingual V3

ثبّت Chatterbox ببيئة منفصلة حتى لا تتعارض إصدارات Torch مع Applio:

```powershell
py -3.11 -m venv .venv-chatterbox
.\.venv-chatterbox\Scripts\python.exe -m pip install --upgrade pip
.\.venv-chatterbox\Scripts\python.exe -m pip install chatterbox-tts
$env:CHATTERBOX_PYTHON = (Resolve-Path ".venv-chatterbox\Scripts\python.exe").Path
```

ينبغي تشغيل أمر تعريف البيئة في نافذة PowerShell نفسها التي ستشغّلين منها الخادم. أعيدي تشغيل الخادم. سيظهر المحرك «مهيأ»، **وذلك لا يعني اجتياز اختبار التوليد**. يحتاج أول تشغيل لتنزيل ملفات النموذج V3 من المصدر.

المصدر: https://github.com/resemble-ai/chatterbox

## 3. محرك تحويل الصوت Applio

ثبتي Applio من مستودعه الرسمي، مع نموذج صوت تملكين إذنًا باستخدامه:
https://github.com/IAHispano/Applio

ضعي ملفات النموذج داخل مجلد logs الخاص بتثبيت Applio، ثم في PowerShell اضبطي المسارات:

```powershell
$env:APPLIO_ROOT = "C:\path\to\Applio"
$env:APPLIO_PYTHON = "C:\path\to\Applio\.venv\Scripts\python.exe"
```

عدلي المسارين إلى مكان تثبيتك الحقيقي؛ اسم مجلد Python يختلف حسب طريقة تنصيب Applio. يعتمد التكامل على الدالة الأصلية run_infer_script ومحرك RVC، ولا يقوم بتحويل صوت تجريبي مزيف.

## 4. القيود والخصوصية

- لا تشغلي هذا الإصدار على عنوان عام أو إنترنت دون حماية بالمصادقة وصلاحيات الملفات.
- الافتراضي http://127.0.0.1:7860 محلي فقط.
- تبقى التسجيلات والنتائج في data حتى تحذفيها يدويًا؛ لا توجد سياسة تنظيف تلقائي بعد.
- عند إعادة تشغيل الخادم تضيع قائمة الوظائف من الذاكرة، رغم بقاء الملفات على القرص.
- حد الرفع 25 ميغابايت، والنص 300 حرف لكل طلب. بعض الامتدادات المدعومة قد تحتاج ترميزات صوتية متوافقة مع المحرك.
- اللهجة العراقية وجودة الاستنساخ تحتاج اختبار تسجيلات واقعية؛ لا توجد مقارنة موثقة مع ElevenLabs.
- لا تستخدمي أصوات أشخاص دون موافقتهم.
- TTS-WebUI وGPT-SoVITS مدرجان بوصفهما محركات مستقبلية غير عاملة بعد.

## 5. اختبارات التطوير

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
