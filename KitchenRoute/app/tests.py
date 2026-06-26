from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Organization, Progress, Recipe, Step, User


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


class RegistrationValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="登録テスト店舗",
            organization_code="REG001",
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
        password_input_index = html.index('name="password"')
        password_confirm_input_index = html.index('name="password_confirm"')
        self.assertGreater(
            html.index("パスワードは8文字以上で入力してください。"),
            password_input_index,
        )
        self.assertLess(
            html.index("パスワードは8文字以上で入力してください。"),
            html.index("パスワードには数字を含めてください。"),
        )
        self.assertGreater(
            html.index("パスワードが一致しません。"),
            password_confirm_input_index,
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

    def test_recipe_update_allows_unchanged_name_and_rejects_other_recipe_name(self):
        unchanged_response = self.client.post(
            reverse("recipe_update", args=[self.recipe.id]),
            {
                "name": "マフィン",
            },
        )

        self.assertRedirects(
            unchanged_response,
            reverse("skill_management"),
            fetch_redirect_response=False,
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

    def test_step_update_allows_unchanged_name_and_rejects_other_step_name(self):
        unchanged_response = self.client.post(
            reverse("step_update", args=[self.step.id]),
            {
                "order": "1",
                "name": "計量",
            },
        )

        self.assertRedirects(
            unchanged_response,
            reverse("step_management", args=[self.recipe.id]),
            fetch_redirect_response=False,
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


class AccountUpdateValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="アカウント変更テスト店舗",
            organization_code="ACC001",
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
