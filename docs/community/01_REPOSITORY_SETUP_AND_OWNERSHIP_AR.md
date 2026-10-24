# إعداد المستودع وحماية نسبة تأسيسه

## الحقيقة القانونية والإدارية
مستودع Mina Voice Studio الأصلي موجود في حساب @ahpa5246-lgtm. اكتبي أن **Mina Hussein Salman هي مؤسسة المشروع وصاحبة فكرته الأصلية**. هذا لا يعني أن مشروع Qwen أو Chatterbox أو RVC ملك لها، أو أن حقوق جميع المساهمين تنتقل إليها تلقائيًا. ترخيص MIT الحالي يسمح بنسخ الكود والتعديل والتوزيع التجاري مع الاحتفاظ بإشعاراته؛ لا يحتكر الفكرة المجردة. هذا شرح عملي لا استشارة قانونية.

## 1 — تعديل صفحة GitHub الرئيسية
من https://github.com/ahpa5246-lgtm/mina-voice-studio اضغطي رمز الترس بجانب About:
- **Description:** Open-source AI voice acting studio for cartoons: design character voices, render multi-speaker scenes and export editable WAV/SRT with local AI models.
- **Website:** لا تضعي رابط localhost أو Kaggle الخاص؛ ضعي رابط Demo علني لاحقًا حين يصبح جاهزًا.
- **Topics:** text-to-speech, voice-cloning, voice-conversion, cartoon, animation, qwen3-tts, chatterbox-tts, rvc, python, open-source, audio-processing, dubbing.
- احفظي وتحققي من ظهورها للزائر غير المسجل.
- **Social preview:** Settings → General → Social Preview: ارفعي صورة PNG/JPG بمقاس 1280×640 وأقل من 1MB تعرض اسم المنتج وشاشة أصلية، ولا تستبدليها بصورة برنامج متخيل.

## 2 — تفعيل Discussions
Settings → General → Features → Discussions / Set up discussions. جهزي الفئات:
- Announcements: الإصدارات والأخبار والإنجازات المثبتة.
- Q&A: أسئلة التثبيت والنماذج وGPU.
- Ideas: المقترحات قبل قبولها كمهام.
- Show and tell: مشاهد صوتية بموافقة أصحاب الحقوق.
- Contributor help: مساعدة المساهمين الجدد.
منشور الترحيب يشرح أين يطرح الزائر سؤالًا وأين يفتح Issue وأين يبلغ عن ثغرة.

## 3 — CODEOWNERS وRulesets
الملف .github/CODEOWNERS يحدد @ahpa5246-lgtm كمراجع لكل الملفات. من Settings → Rules → Rulesets أنشئي قاعدة لفرع main تطلب Pull Request، نجاح اختبارات CI، ومراجعة مالك الكود حيث تدعم الخطة ذلك. **CODEOWNERS وحده لا يمنع الدمج ولا يثبت ملكية قانونية**. تحققّي من عمل قواعد الحماية فعليًا باختبار PR صغير.
لا تعطي صلاحية Admin أو مفاتيح Actions لأي مساهم عابر. العمل الأساسي Fork → PR. راجعي ملفات Actions التي يُعدلها أشخاص آخرون بدقة لأن فيها أسرار Kaggle؛ لا تشغلي كود fork ببيئة أسرار.

## 4 — حقوق المؤسسة والمساهمين
- AUTHORS.md وGOVERNANCE.md يسجلان المؤسس والرؤية الأصلية وطريقة اتخاذ القرار.
- Git history يحفظ تاريخ المساهمات؛ لا تمسحي أسماء مؤلفي الأكواد القديمة أو التراخيص.
- Release notes تسجل اسم كل صاحب مساهمة مهمة.
- إذا أردت حماية اسم Mina Voice Studio تجاريًا لاحقًا، تحققي من تضارب الأسماء واستشيري مختصًا حول العلامات؛ لا تدّعي أنها مسجلة مسبقًا.
- لا تعتمدي على GitHub Stars بوصفها دليلًا قانونيًا على تاريخ الفكرة.

## 5 — أمن المستودع وحساب المؤسسة
- 2FA ونسخة آمنة من Backup Codes وخطة استعادة الحساب.
- أسرار Kaggle داخل Settings → Secrets and variables → Actions فقط؛ ممنوع إدراج التوكن في صور أو issues أو README.
- لا تفتحي خدمة Mina المحلية إلى الإنترنت بلا مصادقة وعزل وتحديد حجم الرفع.
- لا ترفعي عينات صوتية شخصية أو بصمات متحدثين دون إذن.
- راجعي فروع CI واعتماديات المكتبات قبل الدمج.

## 6 — تحقق شهري
- هل الوصف ما زال دقيقًا؟ هل Topics مناسبة؟ هل الروابط تعمل؟
- هل هناك 5 Issues معايير قبولها واضحة؟
- هل CODEOWNERS وRulesets فعليان؟
- هل LICENSE وAUTHORS وGOVERNANCE وSECURITY متاحة؟
- هل التجربة الصوتية قابلة لإعادة التشغيل؟ اختبارات WAV وWER/CER ليست تقييم MOS بشريًا.

### وثائق رسمية
- CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
- Discussions: https://docs.github.com/en/discussions/quickstart
- Topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
- Social preview: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
