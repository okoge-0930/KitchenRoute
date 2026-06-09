from django.test import TestCase
from django.urls import reverse

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
