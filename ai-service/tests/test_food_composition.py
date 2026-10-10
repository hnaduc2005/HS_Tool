from app.food_composition import review_food_composition


def test_declaration_condition_and_model_percentages_do_not_change_recipe_total():
    recipe = 'Cơm chiên: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%.'
    info, _ = review_food_composition(recipe + '\nTình trạng: mới 100%\nModel/Code: FOOD100%\nNhãn hiệu / Xuất xứ: BRAND100%')
    assert info['declared_composition_percent'] == 90
    assert info['undeclared_composition_percent'] == 10
    assert info['declared_shrimp_percent'] == 11
    assert info['declared_pork_percent'] == 10


def test_plain_new_condition_is_not_counted_as_an_ingredient():
    info, _ = review_food_composition('Thực phẩm: gạo 60%; rau 40%; mới 100%')
    assert info['declared_composition_percent'] == 100
from app.rag import preliminary_result
import pytest


@pytest.mark.parametrize('description', [
    'Áo khoác nam: một mặt làm từ vải dệt kim, 100% cotton; mặt kia làm từ vải dệt thoi, 100% cotton.',
    'Áo thun 60% cotton; 40% polyester.',
    'Kệ TV bằng gỗ ghép, ván MDF và ván ép, mới100%.',
])
def test_non_food_percentages_are_not_recipe_composition(description):
    assert review_food_composition(description) == ({}, [])


def test_mixed_rice_shrimp_pork_reports_chapter_16_and_unlisted_ten_percent():
    description = '''Mặt hàng «cơm chiên» đóng gói trong hộp kín khí có thành phần:
    - Gạo: 55%
      Tôm: 11%
    - Thịt lợn: 10%
    - Cà rốt: 5%
    - Hành tây: 5%
    - Gia vị: 4%'''
    normalized, notes = review_food_composition(description)
    assert normalized['declared_composition_percent'] == 90
    assert normalized['declared_animal_percent'] == 21
    assert any('Chú giải 2 Chương 16' in note and '21%' in note for note in notes)
    assert any('1605.29.90' in note for note in notes)
    assert any('10% còn lại' in note for note in notes)


def test_recipe_without_percentages_has_no_generated_legal_conclusion():
    normalized, notes = review_food_composition('Cơm chiên đóng hộp có tôm và thịt lợn')
    assert normalized == {}
    assert notes == []


def test_unavailable_provider_does_not_create_uncited_hypotheses():
    result = preliminary_result(
        'Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%',
        [{'code': '16052990', 'description': 'Loại khác'}],
    )
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert 'provisional_code' not in result['normalized_product']
    assert not result['legal_analysis'].get('hypotheses')
    assert any('10% còn lại' in note for note in result['missing_information'])
