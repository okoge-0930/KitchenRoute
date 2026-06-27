from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class OrganizationScopedModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        if username is None or password is None:
            return None

        users = UserModel._default_manager.filter(
            **{UserModel.USERNAME_FIELD: username}
        )

        if request is not None:
            organization_code = request.POST.get("organization_code")

            if organization_code:
                users = users.filter(
                    organization__organization_code=organization_code
                )

        try:
            user = users.get()
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
