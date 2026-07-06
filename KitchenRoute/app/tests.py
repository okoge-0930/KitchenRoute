import re
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from datetime import timedelta
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend

from .models import Organization, Progress, Recipe, Step, User


class FailingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise Exception("send failed")


def assert_message_between_title_and_form(test_case, response, title, message):
    html = response.content.decode()
    test_case.assertLess(html.index(title), html.index(message))
    test_case.assertLess(html.index(message), html.index("<form"))


class TraineeDetailViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="テスト店舗",
            organization_code="TEST001",
        )
        self.educator = User.objects.create_user(
            username="educator",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.trainee = User.objects.create_user(
            username="trainee",
            password="password",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )

        self.recipe_low = Recipe.objects.create(
            organization=self.organization,
            name="低進捗レシピ",
        )
        self.recipe_high = Recipe.objects.create(
            organization=self.organization,
            name="高進捗レシピ",
        )
        self.recipe_completed = Recipe.objects.create(
            organization=self.organization,
            name="完了レシピ",
        )

        self.low_step_1 = Step.objects.create(
            recipe=self.recipe_low,
            name="低進捗工程1",
            order=1,
        )
        self.low_step_2 = Step.objects.create(
            recipe=self.recipe_low,
            name="低進捗工程2",
            order=2,
        )
        Step.objects.create(
            recipe=self.recipe_low,
            name="低進捗工程3",
            order=3,
        )
        self.high_step_1 = Step.objects.create(
            recipe=self.recipe_high,
            name="高進捗工程1",
            order=1,
        )
        Step.objects.create(
            recipe=self.recipe_high,
            name="高進捗工程2",
            order=2,
        )
        self.completed_step = Step.objects.create(
            recipe=self.recipe_completed,
            name="完了工程",
            order=1,
        )

        Progress.objects.create(
            trainee=self.trainee,
            step=self.low_step_1,
            recorded_by=self.educator,
        )
        Progress.objects.create(
            trainee=self.trainee,
            step=self.high_step_1,
            recorded_by=self.educator,
        )
        Progress.objects.create(
            trainee=self.trainee,
            step=self.completed_step,
            recorded_by=self.educator,
        )

        self.client.force_login(self.educator)

    def test_recipe_progresses_render_collapsed_with_rates(self):
        response = self.client.get(
            reverse("trainee_detail", args=[self.trainee.id])
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        for details in html.split("<details")[1:]:
            details_attributes = details.split(">", 1)[0]
            self.assertNotIn("open", details_attributes)

        self.assertContains(response, "低進捗レシピ")
        self.assertContains(response, "33%")
        self.assertContains(response, "高進捗レシピ")
        self.assertContains(response, "50%")
        self.assertContains(response, "完了済み（1件）")

    def test_mark_step_passed_ajax_updates_only_progress_rate_payload(self):
        response = self.client.post(
            reverse(
                "mark_step_passed",
                args=[self.trainee.id, self.low_step_2.id],
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["progress_rate"], 67)
        self.assertEqual(response.json()["recorded_by"], self.educator.username)
        self.assertTrue(
            Progress.objects.filter(
                trainee=self.trainee,
                step=self.low_step_2,
            ).exists()
        )

    def test_pass_button_shows_confirmation_modal_without_browser_alert(self):
        response = self.client.get(
            reverse("trainee_detail", args=[self.trainee.id])
        )

        self.assertContains(response, "確認")
        self.assertContains(response, "この工程を合格として登録しますか？")
        self.assertContains(response, "登録後は取り消せません。")
        self.assertContains(response, "登録")
        self.assertContains(response, "キャンセル")
        self.assertContains(response, "処理中…")
        self.assertContains(response, "button.disabled = true;")
        self.assertContains(response, "button.disabled = false;")
        self.assertNotContains(response, "alert(")
        self.assertNotContains(response, "confirm(")


class RecipeUpdateViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="レシピ編集テスト店舗",
            organization_code="RECIPE001",
        )
        self.educator = User.objects.create_user(
            username="recipe_editor",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="変更前レシピ",
        )
        self.step = Step.objects.create(
            recipe=self.recipe,
            name="削除確認工程",
            order=1,
        )
        self.client.force_login(self.educator)

    def test_update_from_step_management_redirects_back_to_recipe_steps(self):
        redirect_to = reverse(
            "step_management",
            args=[self.recipe.id],
        )

        response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "変更後レシピ",
                "next": redirect_to,
            },
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.name, "変更後レシピ")
        self.assertRedirects(
            response,
            redirect_to,
            fetch_redirect_response=False,
        )

    def test_update_without_return_path_keeps_recipe_list_redirect(self):
        response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "一覧戻りレシピ",
            },
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.name, "一覧戻りレシピ")
        self.assertRedirects(
            response,
            reverse("skill_management"),
            fetch_redirect_response=False,
        )

    def test_submit_button_state_is_reset_after_history_restore(self):
        response = self.client.get(
            reverse("recipe_update", args=[self.recipe.id])
        )

        self.assertContains(response, "data-disable-on-submit")
        self.assertContains(response, "window.addEventListener(\"pageshow\"")
        self.assertContains(response, "resetDisableOnSubmitForms")
        self.assertContains(response, "button.dataset.originalText")

    def test_recipe_delete_redirects_to_recipe_list(self):
        response = self.client.post(
            reverse("recipe_delete", args=[self.recipe.id])
        )

        self.assertFalse(
            Recipe.objects.filter(id=self.recipe.id).exists()
        )
        self.assertRedirects(
            response,
            reverse("skill_management"),
            fetch_redirect_response=False,
        )

    def test_recipe_delete_get_redirects_without_template_error(self):
        response = self.client.get(
            reverse("recipe_delete", args=[self.recipe.id])
        )

        self.assertTrue(
            Recipe.objects.filter(id=self.recipe.id).exists()
        )
        self.assertRedirects(
            response,
            reverse("skill_management"),
            fetch_redirect_response=False,
        )

    def test_no_change_cancel_returns_to_step_management(self):
        redirect_to = reverse(
            "step_management",
            args=[self.recipe.id],
        )

        response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "変更前レシピ",
                "next": redirect_to,
            },
        )

        self.assertContains(response, "変更前と同じ内容です。")
        html = response.content.decode()
        self.assertIn("location.href=", html)
        self.assertIn("skill\\u002Dmanagement/recipes", html)
        self.assertIn(str(self.recipe.id), html)
        self.assertNotContains(response, "history.back()")

    def test_step_delete_redirects_to_step_list(self):
        response = self.client.post(
            reverse("step_delete", args=[self.step.id])
        )

        self.assertFalse(
            Step.objects.filter(id=self.step.id).exists()
        )
        self.assertRedirects(
            response,
            reverse("step_management", args=[self.recipe.id]),
            fetch_redirect_response=False,
        )

    def test_step_delete_get_redirects_without_template_error(self):
        response = self.client.get(
            reverse("step_delete", args=[self.step.id])
        )

        self.assertTrue(
            Step.objects.filter(id=self.step.id).exists()
        )
        self.assertRedirects(
            response,
            reverse("step_management", args=[self.recipe.id]),
            fetch_redirect_response=False,
        )


class LoginRequiredRedirectTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="ログイン必須確認店舗",
            organization_code="LOGINREQ001",
        )
        self.educator = User.objects.create_user(
            username="login_required_educator",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.trainee = User.objects.create_user(
            username="login_required_trainee",
            password="password",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="ログイン必須レシピ",
        )
        self.step = Step.objects.create(
            recipe=self.recipe,
            name="ログイン必須工程",
            order=1,
        )

    def assert_redirects_to_login(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith(f"{reverse('login')}?next="),
            response["Location"],
        )

    def test_login_required_pages_redirect_to_login_without_500(self):
        get_urls = [
            reverse("educator_home"),
            reverse("trainee_home"),
            reverse("admin_home"),
            reverse("trainee_detail", args=[self.trainee.id]),
            reverse("skill_management"),
            reverse("step_management", args=[self.recipe.id]),
            reverse("recipe_create"),
            reverse("recipe_update", args=[self.recipe.id]),
            reverse("step_create", args=[self.recipe.id]),
            reverse("step_update", args=[self.step.id]),
            reverse("step_delete", args=[self.step.id]),
            reverse("recipe_delete", args=[self.recipe.id]),
            reverse("trainee_task_detail", args=[self.recipe.id]),
            reverse("my_progress"),
            reverse("account"),
            reverse("account_username_update"),
            reverse("account_email_update"),
            reverse("account_password_change"),
        ]

        for url in get_urls:
            with self.subTest(url=url):
                self.assert_redirects_to_login(
                    self.client.get(url)
                )

    def test_login_required_posts_redirect_to_login_without_500(self):
        post_requests = [
            (
                reverse(
                    "mark_step_passed",
                    args=[self.trainee.id, self.step.id],
                ),
                {},
            ),
            (
                reverse("recipe_create"),
                {
                    "name": "未ログインレシピ",
                },
            ),
            (
                reverse("recipe_update", args=[self.recipe.id]),
                {
                    "name": "未ログイン更新",
                },
            ),
            (
                reverse("step_create", args=[self.recipe.id]),
                {
                    "order": "2",
                    "name": "未ログイン工程",
                },
            ),
            (
                reverse("step_update", args=[self.step.id]),
                {
                    "order": "1",
                    "name": "未ログイン工程更新",
                },
            ),
            (
                reverse("step_delete", args=[self.step.id]),
                {},
            ),
            (
                reverse("recipe_delete", args=[self.recipe.id]),
                {},
            ),
            (
                reverse(
                    "change_user_role",
                    args=[self.trainee.id, User.Role.EDUCATOR],
                ),
                {},
            ),
            (
                reverse("account_username_update"),
                {
                    "username": "未ログイン名前",
                },
            ),
            (
                reverse("account_email_update"),
                {
                    "email": "nologin@example.com",
                },
            ),
            (
                reverse("account_password_change"),
                {
                    "old_password": "password",
                    "new_password1": "abc12345",
                    "new_password2": "abc12345",
                },
            ),
        ]

        for url, data in post_requests:
            with self.subTest(url=url):
                self.assert_redirects_to_login(
                    self.client.post(url, data)
                )


class UserSearchViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="検索テスト店舗",
            organization_code="SEARCH001",
        )
        self.educator = User.objects.create_user(
            username="search_educator",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.admin = User.objects.create_user(
            username="search_admin",
            password="password",
            role=User.Role.ADMIN,
            organization=self.organization,
        )
        User.objects.create_user(
            username="target_trainee",
            password="password",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )

    def test_educator_search_result_has_back_to_list_button(self):
        self.client.force_login(self.educator)

        response = self.client.get(
            reverse("educator_home"),
            {"keyword": "target"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "一覧に戻る")
        self.assertContains(response, reverse("educator_home"))

    def test_admin_search_result_has_back_to_list_button(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("admin_home"),
            {"keyword": "target"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "一覧に戻る")
        self.assertContains(response, reverse("admin_home"))

    def test_user_list_without_search_does_not_show_back_to_list_button(self):
        self.client.force_login(self.educator)

        response = self.client.get(reverse("educator_home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "一覧に戻る")

    def test_admin_can_change_user_role_without_template_response_error(self):
        self.client.force_login(self.admin)
        trainee = User.objects.get(username="target_trainee")

        response = self.client.post(
            reverse(
                "change_user_role",
                args=[trainee.id, User.Role.EDUCATOR],
            )
        )

        trainee.refresh_from_db()
        self.assertEqual(trainee.role, User.Role.EDUCATOR)
        self.assertRedirects(
            response,
            reverse("admin_home"),
            fetch_redirect_response=False,
        )


class OrganizationCodeConfirmTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="組織コード確認店舗",
            organization_code="ORGCODE1",
        )
        self.user = User.objects.create_user(
            username="org_user",
            email="org_user@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )

    def test_login_page_has_organization_code_confirm_link(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, "組織コードを忘れた方は")
        self.assertContains(response, reverse("organization_code_confirm"))

    def test_unknown_email_shows_specific_error(self):
        response = self.client.post(
            reverse("organization_code_confirm"),
            {
                "email": "missing@example.com",
                "password": "abc12345",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "入力されたメールアドレスは登録されていません。",
        )

    def test_wrong_password_shows_specific_error(self):
        response = self.client.post(
            reverse("organization_code_confirm"),
            {
                "email": self.user.email,
                "password": "wrong12345",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "パスワードが正しくありません。")

    def test_success_shows_full_code_without_login(self):
        response = self.client.post(
            reverse("organization_code_confirm"),
            {
                "email": self.user.email,
                "password": "abc12345",
            },
        )

        self.assertRedirects(
            response,
            reverse("organization_code_confirm_done"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

        done_response = self.client.get(
            reverse("organization_code_confirm_done")
        )

        self.assertContains(done_response, "組織コード")
        self.assertContains(done_response, "ORGCODE1")
        self.assertContains(
            done_response,
            "上記組織コードをログイン時に入力してください。",
        )
        self.assertContains(done_response, "ログイン画面へ")
        self.assertNotContains(done_response, "None")
        self.assertContains(done_response, "data-copy-organization-code")
        self.assertContains(done_response, "kr-button kr-button--secondary")
        self.assertContains(done_response, "コピー")
        self.assertContains(done_response, "コピーしました。")
        self.assertNotContains(done_response, "kr-message-list--center")


class SuccessMessageLayoutTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="成功メッセージ表示テスト店舗",
            organization_code="SUCCESS001",
        )
        self.educator = User.objects.create_user(
            username="success_educator",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="成功表示レシピ",
        )
        self.client.force_login(self.educator)

    def test_success_messages_are_left_aligned_under_titles(self):
        recipe_response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "成功表示レシピ更新",
            },
            follow=True,
        )

        self.assertContains(recipe_response, "レシピ名を更新しました。")
        self.assertContains(recipe_response, 'class="kr-message-list"')
        self.assertNotContains(recipe_response, "kr-message-list--center")

        step_response = self.client.post(
            reverse("step_create", args=[self.recipe.id]),
            {
                "order": "1",
                "name": "成功表示工程",
            },
            follow=True,
        )

        self.assertContains(step_response, "工程を登録しました。")
        self.assertContains(step_response, 'class="kr-message-list"')
        self.assertNotContains(step_response, "kr-message-list--center")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    PASSWORD_RESET_BASE_URL="https://example.com",
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.organization = Organization.objects.create(
            name="パスワード再設定店舗",
            organization_code="RESET001",
        )
        self.user = User.objects.create_user(
            username="reset_user",
            email="reset@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )

    def test_password_reset_request_validation_messages(self):
        empty_response = self.client.post(
            reverse("password_reset"),
            {
                "email": "",
            },
        )
        invalid_response = self.client.post(
            reverse("password_reset"),
            {
                "email": "invalid-email",
            },
        )
        missing_response = self.client.post(
            reverse("password_reset"),
            {
                "email": "missing@example.com",
            },
        )

        self.assertContains(empty_response, "メールアドレスを入力してください。")
        self.assertContains(
            invalid_response,
            "正しいメールアドレス形式で入力してください。",
        )
        self.assertContains(
            missing_response,
            "入力されたメールアドレスは登録されていません。",
        )

    def test_password_reset_form_sets_and_submits_csrf_cookie(self):
        csrf_client = Client(enforce_csrf_checks=True)
        get_response = csrf_client.get(reverse("password_reset"))

        self.assertEqual(get_response.status_code, 200)
        self.assertIn("csrftoken", get_response.cookies)
        self.assertContains(get_response, 'name="csrfmiddlewaretoken"')

        csrf_token = get_response.cookies["csrftoken"].value
        post_response = csrf_client.post(
            reverse("password_reset"),
            {
                "email": self.user.email,
                "csrfmiddlewaretoken": csrf_token,
            },
        )

        self.assertRedirects(
            post_response,
            reverse("password_reset_done"),
            fetch_redirect_response=False,
        )

    @override_settings(EMAIL_BACKEND="app.tests.FailingEmailBackend")
    def test_password_reset_request_shows_send_failure(self):
        with self.assertLogs("app.views", level="ERROR") as logs:
            response = self.client.post(
                reverse("password_reset"),
                {
                    "email": self.user.email,
                },
            )

        self.assertContains(
            response,
            "メール送信に失敗しました。時間をおいて再度お試しください。",
        )
        self.assertIn(
            "Password reset email send failed.",
            "\n".join(logs.output),
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
        DEFAULT_FROM_EMAIL="",
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=True,
    )
    def test_password_reset_logs_invalid_smtp_configuration(self):
        with self.assertLogs("app.views", level="ERROR") as logs:
            response = self.client.post(
                reverse("password_reset"),
                {
                    "email": self.user.email,
                },
            )

        self.assertContains(
            response,
            "メール送信に失敗しました。時間をおいて再度お試しください。",
        )
        log_output = "\n".join(logs.output)
        self.assertIn("Password reset email configuration is invalid", log_output)
        self.assertIn("EMAIL_HOST is empty.", log_output)
        self.assertIn("EMAIL_HOST_USER is empty.", log_output)
        self.assertIn("EMAIL_HOST_PASSWORD is empty.", log_output)
        self.assertIn(
            "EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true.",
            log_output,
        )

    def test_password_reset_email_link_changes_password_and_allows_login(self):
        response = self.client.post(
            reverse("password_reset"),
            {
                "email": self.user.email,
            },
        )

        self.assertRedirects(
            response,
            reverse("password_reset_done"),
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("KitchenRoute パスワード再設定", mail.outbox[0].subject)

        reset_path = re.search(
            r"https://example.com(?P<path>/reset/[^/]+/[^/]+/)",
            mail.outbox[0].body,
        ).group("path")

        reset_response = self.client.get(reset_path)
        self.assertContains(reset_response, "新しいパスワード")

        rule_response = self.client.post(
            reset_path,
            {
                "new_password1": "aaaaa",
                "new_password2": "aaaaa",
            },
        )
        mismatch_response = self.client.post(
            reset_path,
            {
                "new_password1": "abc12345",
                "new_password2": "abc12346",
            },
        )
        empty_response = self.client.post(
            reset_path,
            {
                "new_password1": "",
                "new_password2": "",
            },
        )

        self.assertContains(
            rule_response,
            "パスワードは8文字以上で入力してください。",
        )
        self.assertContains(rule_response, "パスワードには数字を含めてください。")
        self.assertContains(mismatch_response, "パスワードが一致しません。")
        self.assertContains(empty_response, "パスワードを入力してください。")

        complete_response = self.client.post(
            reset_path,
            {
                "new_password1": "newpass123",
                "new_password2": "newpass123",
            },
        )

        self.assertRedirects(
            complete_response,
            reverse("password_reset_complete"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

        login_response = self.client.post(
            reverse("login"),
            {
                "organization_code": self.organization.organization_code,
                "email": self.user.email,
                "password": "newpass123",
            },
        )

        self.assertRedirects(
            login_response,
            reverse("trainee_home"),
            fetch_redirect_response=False,
        )

    def test_password_reset_invalid_and_expired_url_messages(self):
        invalid_response = self.client.get(
            reverse(
                "password_reset_confirm",
                args=[
                    "invalid-uid",
                    "invalid-token",
                ],
            )
        )

        self.assertContains(invalid_response, "パスワード再設定URLが無効です。")

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            expired_response = self.client.get(
                reverse(
                    "password_reset_confirm",
                    args=[
                        uidb64,
                        token,
                    ],
                )
            )

        self.assertContains(
            expired_response,
            "パスワード再設定URLの有効期限が切れています。",
        )


class RegistrationValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="登録テスト店舗",
            organization_code="REG001",
        )
        self.other_organization = Organization.objects.create(
            name="別登録テスト店舗",
            organization_code="REG002",
        )
        User.objects.create_user(
            username="registered_user",
            email="registered@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )
        User.objects.create_user(
            username="shared_user",
            email="shared@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.other_organization,
        )

    def test_admin_register_shows_all_password_errors_and_keeps_inputs(self):
        response = self.client.post(
            reverse("admin_register"),
            {
                "organization_name": "新規店舗",
                "username": "new_admin",
                "email": "new_admin@example.com",
                "password": "aaaaa",
                "password_confirm": "aaabbb",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        title_index = html.index("管理者用アカウント新規登録")
        form_index = html.index("<form")
        self.assertGreater(
            html.index("パスワードは8文字以上で入力してください。"),
            title_index,
        )
        self.assertLess(
            html.index("パスワードは8文字以上で入力してください。"),
            form_index,
        )
        self.assertLess(
            html.index("パスワードは8文字以上で入力してください。"),
            html.index("パスワードには数字を含めてください。"),
        )
        self.assertGreater(
            html.index("パスワードが一致しません。"),
            title_index,
        )
        self.assertLess(
            html.index("パスワードが一致しません。"),
            form_index,
        )
        self.assertContains(response, 'value="新規店舗"')
        self.assertContains(response, 'value="new_admin"')
        self.assertContains(response, 'value="new_admin@example.com"')

    def test_general_register_shows_organization_code_and_password_errors(self):
        response = self.client.post(
            reverse("general_register"),
            {
                "organization_code": "WRONG001",
                "username": "new_trainee",
                "email": "new_trainee@example.com",
                "password": "abcdefgh",
                "password_confirm": "abcdefgh",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        title_index = html.index("一般用アカウント新規登録")
        form_index = html.index("<form")
        self.assertLess(
            title_index,
            html.index("組織コードが正しくありません。"),
        )
        self.assertLess(
            html.index("組織コードが正しくありません。"),
            form_index,
        )
        self.assertLess(
            html.index("パスワードには数字を含めてください。"),
            form_index,
        )
        self.assertContains(response, "組織コードが正しくありません。")
        self.assertContains(response, "パスワードには数字を含めてください。")
        self.assertNotContains(response, 'value="WRONG001"')
        self.assertContains(response, 'value="new_trainee"')
        self.assertContains(response, 'value="new_trainee@example.com"')

    def test_admin_register_done_uses_created_organization_code(self):
        response = self.client.post(
            reverse("admin_register"),
            {
                "organization_name": "管理者登録完了店舗",
                "username": "done_admin",
                "email": "done_admin@example.com",
                "password": "abc12345",
                "password_confirm": "abc12345",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_register_done"),
            fetch_redirect_response=False,
        )

        done_response = self.client.get(reverse("admin_register_done"))
        organization = Organization.objects.get(name="管理者登録完了店舗")

        self.assertContains(
            done_response,
            f"組織コード：{organization.organization_code}",
        )
        self.assertContains(done_response, reverse("admin_home"))
        self.assertNotContains(done_response, "None")

    def test_admin_register_allows_name_used_in_other_organization(self):
        response = self.client.post(
            reverse("admin_register"),
            {
                "organization_name": "別名許可店舗",
                "username": "shared_user",
                "email": "new_shared_admin@example.com",
                "password": "abc12345",
                "password_confirm": "abc12345",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_register_done"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            User.objects.filter(
                organization__name="別名許可店舗",
                username="shared_user",
            ).exists()
        )

    def test_general_register_rejects_duplicate_name_in_same_organization(self):
        response = self.client.post(
            reverse("general_register"),
            {
                "organization_code": "REG001",
                "username": "registered_user",
                "email": "duplicate_name@example.com",
                "password": "abc12345",
                "password_confirm": "abc12345",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "この名前はすでに登録されています。")
        self.assertEqual(
            User.objects.filter(
                organization=self.organization,
                username="registered_user",
            ).count(),
            1,
        )

    def test_general_register_allows_name_used_in_other_organization(self):
        response = self.client.post(
            reverse("general_register"),
            {
                "organization_code": "REG001",
                "username": "shared_user",
                "email": "new_shared_general@example.com",
                "password": "abc12345",
                "password_confirm": "abc12345",
            },
        )

        self.assertRedirects(
            response,
            reverse("general_register_done"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            User.objects.filter(
                organization=self.organization,
                username="shared_user",
            ).exists()
        )


class RecipeNameValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="レシピ重複テスト店舗",
            organization_code="RECDUP01",
        )
        self.other_organization = Organization.objects.create(
            name="別レシピ重複テスト店舗",
            organization_code="RECDUP02",
        )
        self.educator = User.objects.create_user(
            username="recipe_duplicate_user",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="マフィン",
        )
        self.other_recipe = Recipe.objects.create(
            organization=self.organization,
            name="クッキー",
        )
        self.client.force_login(self.educator)

    def test_recipe_create_rejects_duplicate_name_in_same_organization(self):
        for name in ["  マフィン  ", "まふぃん", "ﾏﾌｨﾝ"]:
            response = self.client.post(
                reverse("recipe_create"),
                {
                    "name": name,
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response,
                "同じレシピ名が既に登録されています。",
            )

        self.assertContains(response, 'value="ﾏﾌｨﾝ"')
        self.assertEqual(
            Recipe.objects.filter(
                organization=self.organization,
                name="マフィン",
            ).count(),
            1,
        )

    def test_recipe_create_requires_name_without_redirect(self):
        response = self.client.post(
            reverse("recipe_create"),
            {
                "name": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "レシピ名を入力してください。")
        assert_message_between_title_and_form(
            self,
            response,
            "レシピ登録",
            "レシピ名を入力してください。",
        )
        self.assertFalse(
            Recipe.objects.filter(
                organization=self.organization,
                name="",
            ).exists()
        )

    def test_recipe_create_treats_english_spelling_as_different_name(self):
        response = self.client.post(
            reverse("recipe_create"),
            {
                "name": "muffin",
            },
        )

        self.assertRedirects(
            response,
            reverse("skill_management"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Recipe.objects.filter(
                organization=self.organization,
                name="muffin",
            ).exists()
        )

    def test_recipe_create_allows_same_name_in_other_organization(self):
        Recipe.objects.create(
            organization=self.other_organization,
            name="フィナンシェ",
        )

        response = self.client.post(
            reverse("recipe_create"),
            {
                "name": "フィナンシェ",
            },
        )

        self.assertRedirects(
            response,
            reverse("skill_management"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Recipe.objects.filter(
                organization=self.organization,
                name="フィナンシェ",
            ).exists()
        )

    def test_recipe_update_shows_no_change_message_and_rejects_other_recipe_name(self):
        unchanged_response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "マフィン",
            },
        )

        self.assertEqual(unchanged_response.status_code, 200)
        self.assertContains(
            unchanged_response,
            "変更前と同じ内容です。",
        )
        assert_message_between_title_and_form(
            self,
            unchanged_response,
            "レシピ編集",
            "変更前と同じ内容です。",
        )

        duplicate_response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "クッキー",
            },
        )

        self.recipe.refresh_from_db()
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(self.recipe.name, "マフィン")
        self.assertContains(
            duplicate_response,
            "同じレシピ名が既に登録されています。",
        )


class StepNameValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="工程重複テスト店舗",
            organization_code="STEPDUP1",
        )
        self.educator = User.objects.create_user(
            username="step_duplicate_user",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="マフィン",
        )
        self.other_recipe = Recipe.objects.create(
            organization=self.organization,
            name="クッキー",
        )
        self.step = Step.objects.create(
            recipe=self.recipe,
            name="計量",
            order=1,
        )
        self.other_step = Step.objects.create(
            recipe=self.recipe,
            name="焼成",
            order=2,
        )
        Step.objects.create(
            recipe=self.other_recipe,
            name="計量",
            order=1,
        )
        self.client.force_login(self.educator)

    def test_step_create_rejects_duplicate_name_in_same_recipe(self):
        for name in ["  計量  ", "けいりょう", "ｹｲﾘｮｳ"]:
            response = self.client.post(
                reverse("step_create", args=[self.recipe.id]),
                {
                    "order": "3",
                    "name": name,
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "同じ工程名が既に登録されています。")

        self.assertContains(response, 'value="ｹｲﾘｮｳ"')
        self.assertFalse(
            Step.objects.filter(
                recipe=self.recipe,
                order=3,
                name="計量",
            ).exists()
        )

    def test_step_create_shows_order_and_name_errors_together(self):
        response = self.client.post(
            reverse("step_create", args=[self.recipe.id]),
            {
                "order": "1",
                "name": "けいりょう",
            },
        )

        self.assertContains(response, "同じ順序の工程がすでに登録されています。")
        self.assertContains(response, "同じ工程名が既に登録されています。")

    def test_step_create_allows_same_name_in_other_recipe(self):
        response = self.client.post(
            reverse("step_create", args=[self.other_recipe.id]),
            {
                "order": "2",
                "name": "焼成",
            },
        )

        self.assertRedirects(
            response,
            reverse("step_management", args=[self.other_recipe.id]),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Step.objects.filter(
                recipe=self.other_recipe,
                name="焼成",
            ).exists()
        )

    def test_step_update_shows_no_change_message_and_rejects_other_step_name(self):
        unchanged_response = self.client.post(
            reverse("step_update", args=[self.step.id]),
            {
                "order": "1",
                "name": "計量",
            },
        )

        self.assertEqual(unchanged_response.status_code, 200)
        self.assertContains(
            unchanged_response,
            "変更前と同じ内容です。",
        )
        assert_message_between_title_and_form(
            self,
            unchanged_response,
            "工程編集",
            "変更前と同じ内容です。",
        )

        duplicate_response = self.client.post(
            reverse("step_update", args=[self.step.id]),
            {
                "order": "1",
                "name": "焼成",
            },
        )

        self.step.refresh_from_db()
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(self.step.name, "計量")
        self.assertContains(
            duplicate_response,
            "同じ工程名が既に登録されています。",
        )

    def test_step_update_changes_name_only(self):
        response = self.client.post(
            reverse("step_update", args=[self.step.id]),
            {
                "order": "1",
                "name": "成形",
            },
        )

        self.step.refresh_from_db()
        self.assertEqual(self.step.order, 1)
        self.assertEqual(self.step.name, "成形")
        self.assertRedirects(
            response,
            reverse("step_management", args=[self.recipe.id]),
            fetch_redirect_response=False,
        )

    def test_step_update_changes_order_only(self):
        response = self.client.post(
            reverse("step_update", args=[self.step.id]),
            {
                "order": "3",
                "name": "計量",
            },
        )

        self.step.refresh_from_db()
        self.assertEqual(self.step.order, 3)
        self.assertEqual(self.step.name, "計量")
        self.assertRedirects(
            response,
            reverse("step_management", args=[self.recipe.id]),
            fetch_redirect_response=False,
        )


class AccountUpdateValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="アカウント変更テスト店舗",
            organization_code="ACC001",
        )
        self.other_organization = Organization.objects.create(
            name="別アカウント変更テスト店舗",
            organization_code="ACC002",
        )
        self.user = User.objects.create_user(
            username="account_user",
            email="account@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )
        User.objects.create_user(
            username="other_user",
            email="used@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )
        User.objects.create_user(
            username="shared_name",
            email="shared-name@example.com",
            password="abc12345",
            role=User.Role.TRAINEE,
            organization=self.other_organization,
        )
        self.client.force_login(self.user)

    def test_username_update_requires_value(self):
        response = self.client.post(
            reverse("account_username_update"),
            {
                "username": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ユーザー名を入力してください。")

    def test_username_update_shows_no_change_message(self):
        response = self.client.post(
            reverse("account_username_update"),
            {
                "username": "account_user",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.username, "account_user")
        self.assertContains(response, "変更前と同じ内容です。")
        assert_message_between_title_and_form(
            self,
            response,
            "名前変更",
            "変更前と同じ内容です。",
        )

    def test_username_update_rejects_duplicate_name_in_same_organization(self):
        response = self.client.post(
            reverse("account_username_update"),
            {
                "username": "other_user",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.username, "account_user")
        self.assertContains(response, "この名前はすでに登録されています。")

    def test_username_update_allows_name_used_in_other_organization(self):
        response = self.client.post(
            reverse("account_username_update"),
            {
                "username": "shared_name",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "shared_name")
        self.assertRedirects(
            response,
            reverse("account"),
            fetch_redirect_response=False,
        )

    def test_email_update_validation_messages(self):
        invalid_response = self.client.post(
            reverse("account_email_update"),
            {
                "email": "invalid-email",
            },
        )
        duplicate_response = self.client.post(
            reverse("account_email_update"),
            {
                "email": "used@example.com",
            },
        )

        self.assertContains(
            invalid_response,
            "正しいメールアドレス形式で入力してください。",
        )
        self.assertContains(
            duplicate_response,
            "このメールアドレスは既に使用されています。",
        )

    def test_email_update_shows_no_change_message(self):
        response = self.client.post(
            reverse("account_email_update"),
            {
                "email": "account@example.com",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.email, "account@example.com")
        self.assertContains(response, "変更前と同じ内容です。")
        assert_message_between_title_and_form(
            self,
            response,
            "メールアドレス変更",
            "変更前と同じ内容です。",
        )

    def test_password_update_shows_specific_errors(self):
        response = self.client.post(
            reverse("account_password_change"),
            {
                "old_password": "wrong12345",
                "new_password1": "aaaaa",
                "new_password2": "aaabbb",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "現在のパスワードが正しくありません。")
        self.assertContains(response, "パスワードは8文字以上で入力してください。")
        self.assertContains(response, "パスワードには数字を含めてください。")
        self.assertContains(response, "パスワードが一致しません。")


class AccountViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="アカウント表示テスト店舗",
            organization_code="ACCVIEW1",
        )

    def test_all_roles_show_organization_code_in_account_view(self):
        for role in [
            User.Role.ADMIN,
            User.Role.EDUCATOR,
            User.Role.TRAINEE,
        ]:
            user = User.objects.create_user(
                username=f"account_view_{role}",
                email=f"account_view_{role}@example.com",
                password="abc12345",
                role=role,
                organization=self.organization,
            )
            self.client.force_login(user)

            response = self.client.get(reverse("account"))

            self.assertContains(response, "所属組織名")
            self.assertContains(response, "組織コード")
            self.assertContains(response, "ACCVIEW1")
            self.assertNotContains(response, "None")

            html = response.content.decode()
            self.assertLess(
                html.index("所属組織名"),
                html.index("組織コード"),
            )
            self.assertLess(
                html.index("組織コード"),
                html.index("名前"),
            )


class StepOrderValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="工程順序テスト店舗",
            organization_code="STEPORDER001",
        )
        self.educator = User.objects.create_user(
            username="step_order_editor",
            password="password",
            role=User.Role.EDUCATOR,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="順序テストレシピ",
        )
        self.step = Step.objects.create(
            recipe=self.recipe,
            name="既存工程",
            order=1,
        )
        self.client.force_login(self.educator)

    def test_step_create_rejects_duplicate_order(self):
        response = self.client.post(
            reverse("step_create", args=[self.recipe.id]),
            {
                "order": "1",
                "name": "重複工程",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "同じ順序の工程がすでに登録されています。")
        self.assertFalse(
            Step.objects.filter(
                recipe=self.recipe,
                name="重複工程",
            ).exists()
        )

    def test_step_update_rejects_duplicate_order(self):
        other_step = Step.objects.create(
            recipe=self.recipe,
            name="別工程",
            order=2,
        )

        response = self.client.post(
            reverse("step_update", args=[other_step.id]),
            {
                "order": "1",
                "name": "別工程",
            },
        )

        other_step.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(other_step.order, 2)
        self.assertContains(response, "同じ順序の工程がすでに登録されています。")


class MyProgressViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="マイ進捗テスト店舗",
            organization_code="MYPROG01",
        )
        self.trainee = User.objects.create_user(
            username="my_progress_trainee",
            password="password",
            role=User.Role.TRAINEE,
            organization=self.organization,
        )
        self.recipe = Recipe.objects.create(
            organization=self.organization,
            name="マフィン",
        )
        self.old_recipe = Recipe.objects.create(
            organization=self.organization,
            name="古いレシピ",
        )
        self.step_1 = Step.objects.create(
            recipe=self.recipe,
            name="生地作成",
            order=1,
        )
        self.step_2 = Step.objects.create(
            recipe=self.recipe,
            name="焼成",
            order=2,
        )
        self.old_step = Step.objects.create(
            recipe=self.old_recipe,
            name="古い工程",
            order=1,
        )
        Progress.objects.create(
            trainee=self.trainee,
            step=self.step_2,
        )
        Progress.objects.create(
            trainee=self.trainee,
            step=self.step_1,
        )
        old_progress = Progress.objects.create(
            trainee=self.trainee,
            step=self.old_step,
        )
        Progress.objects.filter(id=old_progress.id).update(
            passed_at=timezone.now() - timedelta(days=31)
        )
        self.client.force_login(self.trainee)

    def test_recent_section_lists_passed_steps_by_recipe_and_step_order(self):
        response = self.client.get(reverse("my_progress"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "直近30日で合格した工程")
        self.assertNotContains(response, "直近30日の成長")
        self.assertContains(response, "マフィン（2件）")
        self.assertContains(response, "No.1")
        self.assertContains(response, "生地作成")
        self.assertContains(response, "No.2")
        self.assertContains(response, "焼成")
        self.assertNotContains(response, "古いレシピ（1件）")
