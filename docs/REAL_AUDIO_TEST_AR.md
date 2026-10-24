# Real model setup, GPU verification and Kaggle (Arabic)

هذه المرحلة لا تعني أننا درّبنا Qwen أو Applio. **الأولوية أولًا هي اختبار استدلال حقيقي من أوزان جاهزة**، ثم لا نُدرّب نموذجًا جديدًا إلا إذا كشفت القياسات حاجة لذلك وتوفرت بيانات مرخصة.

## 1. تثبيت كل محرك في بيئته المستقلة

مع تثبيت Python 3.11 و3.12 على Windows:

```powershell
py -3.12 scripts/manage_engines.py install qwen
py -3.11 scripts/manage_engines.py install chatterbox
py -3.11 scripts/manage_engines.py install whisper
py -3.11 scripts/manage_engines.py install demucs
py -3.12 scripts/manage_engines.py status
```

بعد كل أمر install سيطبع المسار وأمر تعريف متغير البيئة الخاص بالمحرك؛ نفذيه في نافذة PowerShell التي ستشغل Mina. للاختبار الصوتي الحقيقي، تحتاج النماذج تنزيل أوزانها من المصدر؛ قد يصل الحجم إلى عدة جيجابايت. يمكنك تنزيل وزن Qwen محدد صراحة:

```powershell
py -3.12 scripts/manage_engines.py install qwen --download-weights --checkpoint voice-design
```

**Applio:** ثبتيه من [مستودعه الأصلي](https://github.com/IAHispano/Applio)، ووفري نموذج `.pth` مصرحًا باستخدامه، ثم اضبطي `APPLIO_ROOT` و`APPLIO_PYTHON`. لا نُثبت Applio كما لو كان مجرد حزمة `pip` مستقلة؛ إعداداته تعتمد على نسخته.

## 2. اختبارات GPU فعلية تحفظ دليلًا

شغلي الأمثلة من جذر المستودع بعد تعريف `CHATTERBOX_PYTHON` و`QWEN_PYTHON` و`WHISPER_PYTHON`:

```powershell
python scripts/verify_real_audio.py --engine chatterbox --model multilingual-v3 --language ar --text "مرحبا بكم في حلقتنا الجديدة" --asr
python scripts/verify_real_audio.py --engine qwen --model design --language en --text "Welcome to my cartoon show." --reference-text "A bright, expressive American English cartoon heroine" --asr
python scripts/verify_real_audio.py --engine qwen --model custom --language en --text "This is my original voice." --asr
```

لتجربة Qwen clone أضيفي `--reference` لمسار WAV مخوّل و`--reference-text` لنص المرجع الدقيق، مع `--model clone`. تجربة Applio تتطلب `--engine applio --model MODEL_ID --input-audio own.wav --text "النص المنطوق في الملف"`، مع `--asr` إذا كانت لغة الكلام ar أو en.

كل تشغيل يحفظ `data/_verification/ENGINE/output.wav` و`report.json` يحتوي SHA256 ومدة الصوت والذروة والتقطيع والصمت وزمن التنفيذ وRTF. الخيار `--asr` يستخدم **Faster-Whisper الحقيقي** ويحتاج `python -m pip install -r requirements-audio-eval.txt` في بيئة تطبيق Mina لحساب WER/CER. فشل الأوزان أو GPU أو النموذج ينتج تقرير `failed` ويعيد رمز فشل، وليس بيانات مزيفة. التقرير المحلي ليس إثباتًا مستقلًا لجودة الأداء؛ يجب الاستماع أيضًا. سعة VRAM الكلية قد تظهر؛ استهلاك VRAM الأقصى يظل `null` ما لم نقسّه فعليًا.

صفحة **Engines & Models → Real audio tests** تعرض حالة هذا الدليل المحلي. إن تغير ملف WAV أو أصبح الاختبار أقدم من 30 يومًا، فلن يظهر نجاحًا حديثًا.

## 3. نقل دفتر تجربة الأصوات الإنجليزية إلى Kaggle

توجد الآن GitHub Action باسم **Upload Qwen voice benchmark to Kaggle** وتستطيع رفع دفتر `kaggle/cartoon_voices_qwen3.ipynb` بشكل **خاص**. **الوضع الافتراضي Upload-only** ولا يحرق GPU. عند اختيار `run_gpu=true` يبدأ اختبار استدلال Qwen الصوتي وليس تدريب أوزان.

**لا ترسلي المفتاح في الدردشة.** افتحي GitHub repository → Settings → Secrets and variables → Actions → New repository secret، وأضيفي الاسم الدقيق `KAGGLE_API_TOKEN` وقيمته التوكن الجديد الذي يولده Kaggle من [Settings → API](https://www.kaggle.com/settings/api). إذا كان لديك سر بالاسم `KAGGLE` في مستودع آخر، فهو لا ينتقل تلقائيًا لهذا المستودع.

بعد ذلك: Actions → **Upload Qwen voice benchmark to Kaggle** → **Run workflow** → اكتبي *اسم حساب Kaggle* في `kaggle_username` دون رابط كامل. اتركي `run_gpu=false` لرفع الدفتر فقط. لبدء الاختبار على GPU اختاري `true`. راقبي Kaggle Logs وOutputs؛ لا يكفي نجاح خطوة GitHub لإثبات أن Kaggle أنهى التوليد.

الدفتر يختبر Qwen VoiceDesign وBase clone وCustomVoice مع صوتين اصطناعيين وعدة جمل، ثم يقيس تشابه المتحدث وWER/CER بواسطة Whisper وقياسات الإشارة. **لا يدعم Qwen الرسمي العربية**؛ العربية تختبر محليًا عبر Chatterbox. تدريب RVC يحتاج تسجيلات بيانات مرخصة ومراجعة مستقلة قبل تشغيله.

## 4. قبول النتائج

لا يوجد نجاح شامل آلي لمجرد أن ملف WAV سليم: نراجع ملف الصوت، ونسبة WER/CER، وتشابه المتحدث بين الجمل، والتشوه والتقطيع، ومعدل الزمن الحقيقي، وسلوك GPU، وتقييم استماع A/B أعمى. هذه مقاييس مختلفة لا تختزل في نجمة أو رقم واحد.

## 5. الروابط

- [دفتر Qwen](../kaggle/cartoon_voices_qwen3.ipynb)
- [معايير التقييم](EVALUATION.md)
- [إعداد Applio](INSTALL_AR.md)
