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
- حد الرفع 25 ميغابايت، والنص 6000 حرف لكل طلب؛ يُقسّم داخليًا إلى مقاطع قصيرة. بعض الامتدادات المدعومة قد تحتاج ترميزات صوتية متوافقة مع المحرك.
- اللهجة العراقية وجودة الاستنساخ تحتاج اختبار تسجيلات واقعية؛ لا توجد مقارنة موثقة مع ElevenLabs.
- لا تستخدمي أصوات أشخاص دون موافقتهم.
- TTS-WebUI وGPT-SoVITS مدرجان بوصفهما محركات مستقبلية غير عاملة بعد.

## 5. اختبارات التطوير

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## خصوصية الملفات والتحميل

تزال الملفات المكتملة بعد 24 ساعة **عند تقديم طلبات جديدة**؛ لا توجد مهمة تنظيف مستقلة تعمل عند خمول الخادم. تمت إضافة منع طلبات المواقع الخارجية إلى خادم التشغيل المحلي، لكن التطبيق لم يصبح خدمة سحابية آمنة للمستخدمين المتعددين.

## معيار الجودة

يمكن فحص ملفات WAV المولدة عبر `python scripts/quality_report.py path/to/output.wav`، لكن النتائج لا تقيس الشبه بالمتحدث أو جودة اللهجة العراقية. يلزم اختبار استماع بشري ونسبة خطأ تعرف الكلام (WER) قبل مقارنة الخدمة بأي منتج تجاري.

## تحضير تسجيلات التدريب

بعد جمع تسجيلات تملكين حق استخدامها، خزّنيها خارج GitHub وراجعي `docs/EVALUATION.md`، ثم شغّلي `scripts/dataset_audit.py`. هذا يفحص صلاحية البيانات الأولية فقط؛ لم يُدرب نموذج جديد.

## Chatterbox V3 + Turbo + Nano

Install the original Chatterbox library into an **isolated** Python 3.11 environment. Example on Windows:

```powershell
py -3.11 -m venv .venv-chatterbox
.\.venv-chatterbox\Scripts\python.exe -m pip install chatterbox-tts
$env:CHATTERBOX_PYTHON = (Resolve-Path '.venv-chatterbox\Scripts\python.exe').Path
```

Restart Mina from the same terminal. Select **Multilingual V3** for Arabic and the supported 23-language list. **Turbo** and **Nano** are English-only in their upstream model releases and require an audio reference. The first job loads upstream model weights; later jobs can reuse one warm model in a private subprocess without reloading. Switching models releases the previous model's cache; the Engines screen has a **Unload model** action to free GPU memory.

The automatic subtitles export uses real Faster-Whisper segments: after a successful transcription, click **SRT** or **VTT**. It does not translate, align lips, or generate a voice automatically. For actual generation-quality checks on the RTX GPU, run `scripts/smoke_audio.py` for each model and measure audio content and real-time factor.

## فصل الغناء والموسيقى عبر Demucs

أضيف تبويب «فصل الغناء والموسيقى» الذي يشغل **Demucs الأصلي من Meta**، ولا يصنع نتائج وهمية. ثبتي Demucs في بيئة Python 3.11 خاصة به، مع FFmpeg عند الحاجة:

```powershell
py -3.11 -m venv .venv-demucs
.\.venv-demucs\Scripts\python.exe -m pip install demucs
$env:DEMUCS_PYTHON = (Resolve-Path '.venv-demucs\Scripts\python.exe').Path
```

شغلي Mina من نفس نافذة PowerShell. عند نجاح الفصل ستظهر حزمة ZIP تضم ملف الغناء `vocals.wav` وموسيقى الخلفية `instrumental.wav`. يعتمد جودة الفصل على النموذج والأغنية. نموذج Demucs مفتوح المصدر بترخيص MIT لكن المستودع الأصلي مؤرشف؛ قد تظهر مشكلات توافق مع بعض إصدارات المكتبات الحديثة، ولم نجرب توليد المسارات الفعلي على GPU هنا.

## استوديو شخصيات الكرتون — تجربة حلقة كاملة

1. افتحي **مكتبة الأصوات** واحفظي تسجيلًا مرجعيًا مرخّصًا لكل ممثل أو هوية صوتية مختلفة. التسمية الجديدة من دون مرجع جديد لا تخلق صوتًا مستقلًا.
2. افتحي **استوديو شخصيات الكرتون**، وأنشئي شخصية مرتبطة بالتسجيل، ثم حددي المحرك واللغة والتعبير.
3. أضيفي جمل الحوار بالترتيب، وعيّني الشخصية لكل جملة. يمكن اختيار توجيهات مثل حيوي أو هادئ أو ساخر، لكنها مجرد تقريب باستخدام متغيرات `exaggeration` و`cfg_weight` وليست تحكمًا مضمونًا في المشاعر.
4. اختاري توليد الحلقة. سينتج Chatterbox **كل جملة فعليًا** ويحفظ `episode.wav`، وملفات WAV منفردة للمونتاج، و`dialogue.srt` لترجمة النص بوقته، و`manifest.json`، داخل ZIP واحد.

**الحدود الحالية:** 128 ملف شخصية و128 تسجيلًا محفوظًا و48 جملة لكل توليد (6,000 حرف إجمالًا). إذا لم يكن Chatterbox مثبتًا، تظهر رسالة خطأ واضحة دون ادعاء إنتاج الصوت. قد تختلف جودة النطق باللهجة العراقية واستقرار هوية الشخصية عبر الجمل؛ لا يمكن إثباتها إلا بتجارب استماع حقيقية.

لا توجد الآن ميزة ElevenLabs Voice Design التي تُنشئ هوية صوتية جديدة من وصف مثل «صوت عجوز ساخر». للمقاربة عمليًا استخدمي مرجعًا مرخصًا ومختلفًا لكل شخصية، أو دربي نموذج RVC مصرحًا به عبر Applio، ثم قارني صوت الشخصية في مشاهد مختلفة.

## تصميم صوت كرتوني من وصف نصي

إضافة **Qwen3 VoiceDesign** في تبويب «استوديو شخصيات الكرتون» تنشئ ملف WAV بصوت مبتكر من وصف إنجليزي، دون الحاجة إلى تسجيل صوت شخص. يُحفظ ملف الصوت الجديد في مكتبة الأصوات مع النص المرجعي، وبعدها اختاري نموذج **Qwen Clone** وأحددي الصوت الجديد للشخصية. يولّد Qwen Base الجمل التالية من المرجع نفسه لإبقاء النبرة والهوية ثابتتين قدر الإمكان.

إذا أردتِ تغيير الانفعال لكل جملة، اختاري **Qwen CustomVoice** مع أحد الأصوات الجاهزة مثل Ryan أو Vivian؛ هذا النموذج يدعم التعليمات النصية للغضب والسخرية والحزن والبكاء. لكنه لا يضمن المحافظة على صوت مُصمّم جديد، لأن **Qwen Base Clone لا يدعم هذه التعليمات الانفعالية**.

نماذج Qwen3-TTS الرسمية لا تدعم العربية ضمن لغاتها العشر، لذا بقي Chatterbox متاحًا للغة العربية. تثبيت Qwen منفصل ضروري:

```powershell
py -3.12 -m venv .venv-qwen
.\.venv-qwen\Scripts\python.exe -m pip install qwen-tts soundfile
$env:QWEN_PYTHON = (Resolve-Path '.venv-qwen\Scripts\python.exe').Path
```

اقرئي الخطوات الكاملة لتجربة GPU المجانية وتقرير ثبات الهوية في [دليل Qwen/Kaggle](QWEN_KAGGLE_AR.md).
