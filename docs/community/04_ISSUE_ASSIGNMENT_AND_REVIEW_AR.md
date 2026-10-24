# كيف تمنحين المطورين مهامًا فعلية وتديرين Pull Requests؟

## 1. اختاري المهمة قبل فتح Issue
افتحي [بنك 30 مهمة](03_CONTRIBUTOR_TASK_CATALOG_AR.md) وابحثي عن شيء لم يُنفّذ بعد في main، ولا يتطلب ملفات صوت خاصة أو GPU إذا كان لمساهم مبتدئ. ركزي على تغيير واحد محدد. لا تُعطي 20 مهمة لشخص واحد في بداية تعاونه. صفي وظيفة الميزة ونتيجة اختبارها بدل كتابة "حسن المشروع كله".

## 2. افتحي الـIssue حرفيًا
الرابط: https://github.com/ahpa5246-lgtm/mina-voice-studio/issues/new/choose
- اختاري قالب Feature request أو Bug report عند ملاءمته؛ للمهمة المحددة يمكن اختيار Blank Issue إن كان متاحًا، أو تحرير القالب بحسب الحاجة.
- **Title مثال:** Beginner: improve Arabic install troubleshooting with verified commands.
- **Description:** مشكلة + سيناريو مستخدم + الملفات المحتمل تغييرها + نطاق العمل + أمثلة قبل/بعد + معيار قبول + اختبارات + ما لا نريد تغييره.
- **Labels:** good first issue للمهام البسيطة جدًا، help wanted للمستوى المتوسط، documentation, testing, accessibility, audio, model-integration, priority:P0 بعد إنشاء هذه الوسوم. لا تضيفي وسومًا غير موجودة دون تعريفها.
- **Milestone/Project:** Phase 0 Installation أو Phase 1 Cartoon Workflow حسب خارطة الطريق، إذا تم إنشاء Milestones أو Project مسبقًا.
- عيّني نفسك للمراجعة، ثم كلفي المساهم عند موافقته وحين يسمح GitHub بالتعيين.

## 3. إنشاء الوسوم من GitHub
Issues → Labels → New label. الأسماء المقترحة:
| Label | متى؟ |
|---|---|
| good first issue | إصلاح صغير، مواصفات مستقرة، لا GPU، مثال اختبار موجود |
| help wanted | مهمة جاهزة يمكن لشخص خارجي تنفيذها |
| documentation | README ودلائل التثبيت |
| accessibility | keyboard/ARIA/contrast |
| i18n | عربي/إنجليزي وRTL |
| audio | معالجة WAV والتحويل |
| engine:Qwen | محرك Qwen |
| engine:Chatterbox | محرك Chatterbox |
| engine:Applio | Applio/RVC |
| testing | اختبارات وانحدار |
| priority:P0 / P1 / P2 | أولوية الحل وليس صعوبة الشخص |
| needs reproduction | تقرير مشكلة غير قابل لإعادة الإنتاج بعد |
| needs design | الفكرة تحتاج نقاش قبل كود |
| blocked:GPU | يحتاج GPU أو وزن نموذج حقيقي |
| security | ملاحظة أمنية غير سرية، لا تنشري ثغرة حساسة |
| in progress | يوجد مساهم يعمل وفق تعليق علني |

## 4. قبول متطوع للمهمة دون إعطاء صلاحيات المستودع
عندما يعلّق شخص، اطلبي خطة قصيرة ومخرجات اختبار. إن كانت المهمة غير مشغولة، اكتبي:
"Thanks for volunteering. Please keep the change to X, add test Y and link this issue from your PR. I'll review for correctness and licensing. Let us know if you're blocked."
الأفضل تحديد فترة نشاط مرنة (مثل 7 أيام للتحديث، لا موعد إلزامي)؛ إن اختفى المساهم اكتبي تعليقًا مهذبًا قبل إعادة فتح التكليف.

**مهم:** GitHub Issue Assignees قد لا يسمح بتعيين حساب لم يتفاعل مع المستودع أو ليس ضمن الصلاحيات المناسبة. التعليق العلني وحالة in progress كافيان إن تعذر التعيين. لا تدعِي صلاحية Admin شرطًا للمشاركة.

## 5. خطوات المساهم — باللغة الإنجليزية
1. Read CONTRIBUTING and claim an issue in a comment.
2. Fork the repo and create a branch: git checkout -b fix/arabic-install.
3. Run baseline tests: python -m pip install -r requirements-dev.txt; python -m pytest -q.
4. Edit only requested scope; add positive and negative test cases; never commit large weights/tokens/private recordings.
5. Commit with a clear message and open a Pull Request to original main.
6. Explain the bug, behavior before and after, tests performed, limitations, license changes, screenshots when relevant.
7. Address review feedback and wait for green CI.

## 6. قواعد مراجعة طلب السحب
- هل PR تعالج Issue واحدة؟ إن تجاوزت آلاف الأسطر بلا داعٍ اطلبي تقسيمًا.
- هل أصلحت الخطأ بالفعل أم أضافت زرًا شكليًا؟
- اختبارات Pythons وChromium خضراء؟ وهل الاختبار Neural حقيقي أم Mock؟ لا تخلطيهما.
- هل تغير نموذج أو SDK خارجي؟ تحققي من API ورخصته والتوافق.
- هل البيانات آمنة؟ منع Path traversal ورفع ملفات كبيرة وجمع أصوات خاصة.
- هل الرسائل ثنائية اللغة وRTL؟ هل سلوك الفشل واضح؟
- هل يوجد تعليق توضيحي وإشادة بالمساهم بعد الدمج؟

## 7. قوالب ردود مختصرة
**استقبال:** "Welcome! This issue is open. Please share a short implementation plan; we can help you find the relevant files."
**تحديد نطاق:** "Thanks. Could you keep the PR limited to [scope] and add regression test [name]?"
**طلب تعديل:** "The UI change works, but the missing-model path still reports success. Please return an explicit failure and add a test."
**قبول:** "Merged. Thank you for the fix and tests. Your contribution will be credited in the next release notes."
**تأخر الرد:** "Thanks for your patience. This is still pending review; I'll update the issue when I can. Feel free to leave reproducible findings."
**حجز منتهي:** "Are you still working on this? If not, we can make it available to another contributor."

## 8. أمثلة لاستخدام GitHub CLI — اختيارية
بعد تسجيل الدخول بالأمر gh auth login:
- إنشاء مهمة من ملف محلي: gh issue create --repo ahpa5246-lgtm/mina-voice-studio --title "Improve install errors" --body-file issue.md --label "good first issue"
- عرض مهام المبتدئين: gh issue list --repo ahpa5246-lgtm/mina-voice-studio --label "good first issue"
- عرض PRs: gh pr list --repo ahpa5246-lgtm/mina-voice-studio
- **لا** تضعي التوكن في سطر الأمر أو ملف issue.md.
الوسم يجب أن يكون موجودًا مسبقًا؛ إن لم يكن، أنشئيه من واجهة GitHub أولًا.

## 9. حماية المؤسسة دون قتل المجتمع
لا تدمجي كودًا لم تختبريه لتكثري عدد المساهمين؛ لا تحجزي جميع المهام باسمك؛ لا تطلبي Star مقابل مراجعة أو قبول. أعطي المساهم امتنانًا وحقه في سجل التاريخ، مع بقاء قرار دمج النسخة الأصلية للمشرفة.
