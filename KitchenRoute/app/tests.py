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
