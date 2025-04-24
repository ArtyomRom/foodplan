from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from users.models import Profile, Category  # путь к твоей модели
from recipes.models import Recipe  # путь к модели рецептов
import random
from aiogram import types
import logging
from aiogram.types import InputFile
from pathlib import Path
from django.db import IntegrityError
router = Router()

logger = logging.getLogger(__name__)

class RegisterState(StatesGroup):
    first_name = State()
    last_name = State()
    email = State()

# Кнопки оплаты
def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить сейчас", callback_data="pay_now")],
        [InlineKeyboardButton(text="⏳ Оплатить потом", callback_data="pay_later")]
    ])

# Проверка и создание пользователя по telegram_id
@sync_to_async
def get_or_create_user_by_telegram_id(telegram_id):
    try:
        profile = Profile.objects.get(telegram_id=str(telegram_id))
        return profile, True
    except Profile.DoesNotExist:
        return None, False

# Создание пользователя и профиля с защитой от уникальности

@sync_to_async
def create_user_with_profile(telegram_id, first_name, last_name, email):
    user_model = get_user_model()

    # Проверка, существует ли уже профиль с таким telegram_id
    try:
        profile = Profile.objects.get(telegram_id=int(telegram_id))  # Проверяем по telegram_id
        user = profile.user  # Получаем связанного пользователя
        return profile  # Возвращаем уже существующий профиль
    except Profile.DoesNotExist:
        # Если профиль не найден, создаем нового пользователя
        user, created = user_model.objects.get_or_create(
            username=email,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        # Создаем новый профиль, если его нет
        profile, created = Profile.objects.get_or_create(
            user=user,  # Связываем профиль с уже существующим пользователем
            defaults={'telegram_id': int(telegram_id)}  # Если профиль не найден, создаем с этим telegram_id
        )


        if not profile.telegram_id:
            profile.telegram_id = int(telegram_id)
            profile.save()

        return profile
@router.message(Command('start'))
async def get_choice_free_or_premium(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Бесплатная версия", callback_data='recipe')],
            [InlineKeyboardButton(text="Premium версия", callback_data='premium')],
        ]
    )
    await message.answer(
        "Привет 👋\n"
        "Я помогу тебе с рецептами на каждый день!\n\n"
        "🔹 Хочешь получить рецепт дня?\n"
        "🔹 Нужен список покупок?\n"
        "🔹 Или хочешь указать предпочтения (веган, без глютена)?\n\n"
        "Выбирай команду ниже или жми кнопку меню!",
        reply_markup=keyboard
    )

@sync_to_async
def get_user_first_name(profile):
    return profile.user.first_name or profile.user.username

@router.callback_query(lambda c: c.data == "premium")
async def handle_premium(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = str(callback.from_user.id)
    profile, exists = await get_or_create_user_by_telegram_id(telegram_id)

    if exists:
        user_first_name = await get_user_first_name(profile)
        await callback.message.answer(
            f"👋 Добро пожаловать обратно, {user_first_name}!",
            reply_markup=get_payment_keyboard()
        )
    else:
        await state.set_state(RegisterState.first_name)
        await callback.message.answer("📝 Введите ваше имя:")

@router.message(RegisterState.first_name)
async def register_first_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await state.set_state(RegisterState.last_name)
    await message.answer("Введите вашу фамилию:")

@router.message(RegisterState.last_name)
async def register_last_name(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await state.set_state(RegisterState.email)
    await message.answer("Введите ваш Email:")

@router.message(RegisterState.email)
async def register_email(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)

    # Проверка: если профиль уже существует, выходим из регистрации
    existing_profile, exists = await get_or_create_user_by_telegram_id(telegram_id)
    if exists:
        await state.clear()
        user_first_name = await get_user_first_name(existing_profile)
        await message.answer(
            f"👋 Добро пожаловать обратно, {user_first_name}!",
            reply_markup=get_payment_keyboard()
        )
        return

    data = await state.get_data()

    try:
        await create_user_with_profile(
            telegram_id=telegram_id,
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=message.text
        )
        await message.answer("✅ Регистрация завершена!", reply_markup=get_payment_keyboard())
    except Exception as e:
        await message.answer(f"Ошибка при создании пользователя: {e}")
    finally:
        await state.clear()


@sync_to_async
def get_all_categories():
    return list(Category.objects.all())


@router.callback_query(lambda c: c.data == "pay_now")
async def handle_pay_now(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔐 Отлично! Сейчас покажем категории блюд!")

    categories = await get_all_categories()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat.name, callback_data=f"category_{cat.id}")]
        for cat in categories
    ])

    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)

@sync_to_async
def get_recipes_by_category_id(category_id):
    return list(Recipe.objects.filter(categories__id=category_id).distinct()[:3])

@router.callback_query(lambda c: c.data.startswith("category_"))
async def handle_category(callback: types.CallbackQuery):
    await callback.answer()
    category_id = int(callback.data.split("_")[1])
    recipes = await get_recipes_by_category_id(category_id)

    if recipes:
        for recipe in recipes:
            caption = f"🍽 {recipe.title}\n💰 ~{recipe.estimated_cost} ₽"

            if recipe.image and Path(recipe.image.path).exists():
                photo = FSInputFile(recipe.image.path)
                await callback.message.answer_photo(photo=photo, caption=caption)
                # Получаем шаги
                steps = await sync_to_async(list)(recipe.steps.all())

                # Отправляем шаги
                for step in steps:
                    text = step.text
                    if step.image and Path(step.image.path).exists():
                        step_photo = FSInputFile(step.image.path)
                        await callback.message.answer_photo(photo=step_photo, caption=text)
                    else:
                        await callback.message.answer(text)
            else:
                await callback.message.answer(caption)
    else:
        await callback.message.answer("Пока нет рецептов в этой категории.")

@router.callback_query(lambda c: c.data == "pay_later")
async def handle_pay_later(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Хорошо, вы всегда можете вернуться к подписке в разделе «Профиль» 🧾")

@sync_to_async
def get_random_recipe_data():
    recipes = list(Recipe.objects.all())
    if not recipes:
        return None

    recipe = random.choice(recipes)

    def get_unit_display(unit_code):
        UNIT_CHOICES = [
            ("pcs", "шт."),
            ("g", "г"),
            ("kg", "кг"),
            ("tsp", "ч. л."),
            ("tbsp", "ст. л."),
            ("cup", "стакан"),
        ]
        for code, name in UNIT_CHOICES:
            if code == unit_code:
                return name
        return unit_code

    ingredients = [
        f"• {ri.ingredient.name} — {ri.amount} {get_unit_display(ri.unit)}"
        for ri in recipe.recipeingredient_set.all()
    ]

    steps = [
        f"{s.order}. {s.text}" for s in recipe.steps.all().order_by("order")
    ]

    return {
        "title": recipe.title,
        "ingredients": ingredients,
        "steps": steps,
        "image": FSInputFile(recipe.image.path) if recipe.image else None,
        "step_images": [
            FSInputFile(s.image.path) if s.image else None for s in recipe.steps.all().order_by("order")
        ],
        "price": recipe.estimated_cost,
    }

@router.callback_query(lambda c: c.data == "recipe")
async def get_recipe(callback: types.CallbackQuery):
    await callback.answer()

    recipe_data = await get_random_recipe_data()

    if recipe_data:
        ingredients = "\n".join(recipe_data['ingredients'])
        message = f"🍽️ Рецепт дня: {recipe_data['title']}\n\n{ingredients}"

        if recipe_data['image']:
            await callback.message.answer_photo(
                photo=recipe_data['image'],
                caption=message
            )
        else:
            await callback.message.answer(message)

        for step, step_image_url in zip(recipe_data['steps'], recipe_data['step_images']):
            step_message = f"{step}\n"
            if step_image_url:
                await callback.message.answer_photo(photo=step_image_url, caption=step_message)
            else:
                await callback.message.answer(step_message)

    else:
        await callback.message.edit_text("Извините, рецепты сейчас недоступны.")

    price = f'Общая стоимость блюда {recipe_data["price"]} руб.'
    await callback.message.answer(price)
