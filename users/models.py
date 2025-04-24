from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    """
    Централизованная модель категорий (Веган, Без глютена, Эконом и т.п.).
    """
    name = models.CharField(_("Название категории"), max_length=50, unique=True)

    class Meta:
        verbose_name = _("Категория")
        verbose_name_plural = _("Категории")
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    """
    Расширение стандартного User для наших нужд.
    """
    telegram_id = models.BigIntegerField(
        _("Telegram ID"),
        unique=True,
        null=True,
        blank=True,
        help_text=_("Уникальный Telegram ID пользователя")
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_("Пользователь")
    )

    categories = models.ManyToManyField(
        Category,
        verbose_name=_("Категории"),
        blank=True,
        help_text=_("Выберите категории блюд, которые вам интересны")
    )

    liked = models.ManyToManyField(
        'recipes.Recipe',
        related_name='liked_by',
        blank=True,
        verbose_name=_("Лайки")
    )
    disliked = models.ManyToManyField(
        'recipes.Recipe',
        related_name='disliked_by',
        blank=True,
        verbose_name=_("Дизлайки")
    )

    swap_count = models.PositiveSmallIntegerField(
        _("Число замен"), default=0
    )
    paid_until = models.DateField(
        _("Подписка до"), null=True, blank=True
    )
    last_free_recipe = models.DateField(
        _("Последний бесплатный рецепт"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Профиль")
        verbose_name_plural = _("Профили")

    def __str__(self):
        return self.user.username

    def is_active_subscriber(self) -> bool:
        return self.paid_until and self.paid_until >= timezone.now().date()

    def can_get_free_recipe(self) -> bool:
        today = timezone.now().date()
        return not self.last_free_recipe or self.last_free_recipe < today

    def mark_free_recipe_given(self) -> None:
        self.last_free_recipe = timezone.now().date()
        self.save(update_fields=['last_free_recipe'])
