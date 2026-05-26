from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class Organization(models.Model):
    """店舗・学校・会社など、ユーザーが所属する組織を表します。"""

    # 組織名です。例: 「Aベーカリー」「KitchenRoute製菓学校」
    name = models.CharField(max_length=100, unique=True)

    # 組織データを作成した日時です。自動で現在日時が保存されます。
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # データベース上のテーブル名を指定します。
        db_table = "organizations"

    def __str__(self):
        # 管理画面などで表示される名前です。
        return self.name


class User(AbstractUser):
    """ログインするユーザーを表します。新人・教育者・管理者をroleで分けます。"""

    class Role(models.IntegerChoices):
        # 0: 新人。自分の進捗や次に習得すべき工程を確認します。
        TRAINEE = 0, "新人"

        # 1: 教育者。新人に対して工程の合格記録を付けます。
        EDUCATOR = 1, "教育者"

        # 2: 管理者。教育者と同じ操作に加えて、管理者として扱います。
        ADMIN = 2, "管理者"

    # 所属組織です。同じ組織内のユーザー・レシピ・工程を扱うために使います。
    # null=True / blank=True にしておくと、最初のスーパーユーザー作成時にも困りにくいです。
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    # ユーザーの役割です。0: 新人、1: 教育者、2: 管理者を保存します。
    role = models.PositiveSmallIntegerField(choices=Role.choices, default=Role.TRAINEE)

    class Meta:
        # Django標準のauth_userではなく、指定されたusersテーブルを使います。
        db_table = "users"

    def is_trainee(self):
        # 新人かどうかを判定します。ビューでroleの数字を直接書かずに済みます。
        return self.role == self.Role.TRAINEE

    def is_educator_or_admin(self):
        # 教育者または管理者かどうかを判定します。
        return self.role in [self.Role.EDUCATOR, self.Role.ADMIN]

    def progress_rate(self):
        # 自分の組織にある全工程のうち、合格済み工程が何%かを返します。
        if self.organization is None:
            return 0

        total_steps = Step.objects.filter(recipe__organization=self.organization).count()
        if total_steps == 0:
            return 0

        passed_steps = Progress.objects.filter(trainee=self).count()
        return round(passed_steps / total_steps * 100)

    def next_step(self):
        # まだ合格していない工程のうち、最初に取り組む工程を1件返します。
        if self.organization is None:
            return None

        passed_step_ids = Progress.objects.filter(trainee=self).values_list("step_id", flat=True)
        return (
            Step.objects.filter(recipe__organization=self.organization)
            .exclude(id__in=passed_step_ids)
            .order_by("recipe__id", "order", "id")
            .first()
        )


class Recipe(models.Model):
    """教育対象となるレシピを表します。例: ショートケーキ、クロワッサンなど。"""

    # このレシピを使う組織です。組織ごとにレシピを分けるために使います。
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="recipes",
    )

    # レシピ名です。例: 「基本のスポンジ生地」
    name = models.CharField(max_length=100)

    # レシピの補足説明です。不要な場合は空欄で保存できます。
    description = models.TextField(blank=True)

    # レシピを作成した日時です。自動で現在日時が保存されます。
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # データベース上のテーブル名を指定します。
        db_table = "recipes"

        # 一覧表示では、作成が古い順に並べます。
        ordering = ["id"]

    def __str__(self):
        # 管理画面などで表示される名前です。
        return self.name


class Step(models.Model):
    """レシピごとの工程を表します。新人はこの工程単位で合格記録を付けられます。"""

    # どのレシピに属する工程かを表します。
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    # 工程名です。例: 「材料を計量する」「生地を混ぜる」
    name = models.CharField(max_length=100)

    # 工程の順番です。小さい数字から順に表示します。
    order = models.PositiveIntegerField(default=1)

    # 工程の詳しい説明です。手順や合格基準を書けます。不要な場合は空欄で保存できます。
    description = models.TextField(blank=True)

    # 工程を作成した日時です。自動で現在日時が保存されます。
    created_at = models.DateTimeField(auto_now_add=True)

    # 工程を編集した日時です。保存するたびに自動で更新されます。
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # データベース上のテーブル名を指定します。
        db_table = "steps"

        # 工程一覧では、レシピごとにorderの小さい順で並べます。
        ordering = ["recipe", "order", "id"]

    def __str__(self):
        # 管理画面などで「レシピ名 - 工程名」と表示します。
        return f"{self.recipe.name} - {self.name}"


class Progress(models.Model):
    """新人がどの工程に合格したかを記録します。"""

    # 合格した新人です。roleが新人のユーザーを想定しています。
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="progresses",
    )

    # 合格した工程です。
    step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
        related_name="progresses",
    )

    # 合格を記録した日時です。記録作成時に自動で現在日時が保存されます。
    passed_at = models.DateTimeField(auto_now_add=True)

    # 合格を記録した教育者または管理者です。
    # 記録者ユーザーが削除されても、合格記録自体は残すためSET_NULLにしています。
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_progresses",
        null=True,
    )

    class Meta:
        # データベース上のテーブル名を指定します。
        db_table = "progresses"

        # 同じ新人に対して、同じ工程の合格記録を重複して作らないための指定です。
        unique_together = ("trainee", "step")

        # 新しい合格記録が上に来るように並べます。
        ordering = ["-passed_at"]

    def __str__(self):
        # 管理画面などで「新人名 - 工程名」と表示します。
        return f"{self.trainee.username} - {self.step.name}"