"""Conservative arithmetic checks for mixed food descriptions."""

import re


def review_food_composition(description: str) -> tuple[dict, list[str]]:
    # Percentages for textile layers, material blends and goods marked "mới 100%"
    # are not food recipes and must not trigger recipe arithmetic or Chapter 16.
    if not re.search(r'(?<!\w)(?:cơm|gạo|tôm|thịt|cà rốt|hành tây|gia vị|tiêu|ớt|thực phẩm|thức ăn|đồ uống)(?!\w)', description.lower()):
        return {}, []
    components: list[tuple[str, float]] = []
    for fragment in re.split(r'[;\n]', description.lower()):
        # Declaration metadata percentages (notably "mới 100%") are not
        # recipe ingredients, even when the rest of the description is food.
        if re.match(r'\s*(?:tình trạng|condition|model(?:/code)?|model|mã sản phẩm|'
                    r'nhãn hiệu(?:\s*/\s*xuất xứ)?|brand|xuất xứ|origin|tên tiếng việt|'
                    r'công dụng\s*/\s*thông số kỹ thuật)\s*[:=]', fragment):
            continue
        match = re.search(r'([^\d%:]+?)\s*:?\s*(\d+(?:[.,]\d+)?)\s*%', fragment)
        if match:
            if re.fullmatch(r'(?:hàng\s+)?mới|(?:brand[- ]?)?new', match.group(1).strip(' -•:')):
                continue
            components.append((match.group(1).strip(' -•:').strip(), float(match.group(2).replace(',', '.'))))
    if not components:
        return {}, []

    total = round(sum(weight for _, weight in components), 2)
    shrimp = sum(weight for label, weight in components if 'tôm' in label)
    pork = sum(weight for label, weight in components if re.search(r'thịt\s*(?:lợn|heo)', label))
    normalized = {'declared_composition_percent': total}
    notes: list[str] = []
    if shrimp and pork:
        animal = round(shrimp + pork, 2)
        normalized.update({'declared_shrimp_percent': shrimp, 'declared_pork_percent': pork, 'declared_animal_percent': animal})
        if animal > 20:
            notes.append(
                f'Theo Chú giải 2 Chương 16 của Nghị định 26/2023/NĐ-CP, phần đã khai có tôm {shrimp:g}% '
                f'và thịt lợn {pork:g}%, tổng {animal:g}% vượt ngưỡng 20%; cần xét Chương 16 trước nhóm hàng từ gạo thuộc Chương 19.'
            )
            if shrimp > pork and re.search(r'(?:hộp|bao bì)\s*kín\s*khí', description.lower()):
                notes.append(
                    'Trong các thành phần động vật đã khai, tôm chiếm tỷ lệ lớn hơn thịt lợn. '
                    'Nếu thành phần chưa khai không làm thay đổi ưu thế này và hàng thực sự đóng bao bì kín khí, '
                    'nhánh cần đối chiếu là 1605.29; mã 1605.29.90 áp dụng cho loại khác, không phải tôm dạng viên hay tôm tẩm bột.'
                )
    if total < 99.99:
        normalized['undeclared_composition_percent'] = round(100 - total, 2)
        if shrimp and pork and pork + 100 - total > shrimp:
            notes.append(
                f'Giả định về dữ kiện: nếu toàn bộ {100 - total:g}% còn thiếu là thịt lợn thì tổng thịt lợn '
                f'là {pork:g}% + {100 - total:g}% = {pork + 100 - total:g}%, lớn hơn tôm {shrimp:g}%. '
                f'Thêm thịt loài khác không làm tăng riêng tỷ lệ thịt lợn; phải xét lại từng loại hoặc nhóm thành phần phù hợp.'
            )
        notes.append(
            f'Các tỷ lệ thành phần mới cộng {total:g}%; cần xác nhận {100 - total:g}% còn lại '
            'trước khi chốt mã tám số, đặc biệt nếu phần này có thêm thịt hoặc thủy sản.'
        )
    elif total > 100.01:
        notes.append(f'Các tỷ lệ thành phần cộng {total:g}%, vượt 100%; cần kiểm tra lại công thức.')
    return normalized, notes
