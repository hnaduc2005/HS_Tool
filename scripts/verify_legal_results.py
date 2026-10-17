"""Smoke check the running local stack without exposing credentials."""
import json
import argparse
import os
from pathlib import Path
import httpx

samples = {
    'fried-rice': 'Căn cứ vào danh mục hàng hóa xuất nhập khẩu VN và các tài liệu pháp lý có liên quan hãy phân loại vào phân nhóm thích hợp mặt hàng «cơm chiên» đóng gói trong hộp kín khí có thành phần: Gạo: 55%; Tôm: 11%; Thịt lợn: 10%; Cà rốt: 5%; Hành tây: 5%; Gia vị: 4%.',
    'unclear-product': 'Một thiết bị đa năng chưa có thông số kỹ thuật, chưa rõ công dụng chính và vật liệu cấu tạo.',
    'complete-food': 'Cơm chiên đã nấu chín, ăn ngay, đóng hộp kín khí. Tỷ lệ theo khối lượng thành phẩm: gạo 65%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%. Không có thành phần khác; không phải tôm dạng viên hoặc tôm tẩm bột; không phải súp, nước xốt hay pasta nhồi.',
    'tv-console': 'CG-300 TV CONSOLE- Kệ TV CG-300 QC:(1524*457*864H)mm,(gỗ ghép (gỗ dương),ván MDF,ván ép),không nhãn hiệu,có nhãn hàng hóa,mới100%- QC:(1524*457*864H)MM',
    'reversible-jacket': 'Áo khoác nam:\n- Một mặt (A) làm từ vải dệt kim, 100% cotton (61.01)\n- Mặt kia (B) làm từ vải không dệt kim, 100% cotton (61.02)\n- Hai mặt này có túi như nhau và đều thêu logo bên ngực trái.',
    'mixed-spices': 'Phân loại hỗn hợp gia vị gồm:\n- 50% tiêu (0904.12)\n- 50% ớt (0904.22)',
    'gift-set': 'Bộ quà tặng gồm caravat và vớ',
    'servo-motor': 'HIGH EFFICIENCY PERMANENT\nMAGNET SYNCHRONOUS SERVO\nMOTOR, MODEL: TVF225M-8-45-152',
    'pneumatic-valve': 'PNEUMATIC VALVE φ350',
    'inverter': 'INVERTER, MODEL: JK200A-075-4T',
    'frequency-converter': 'VARIABLE FREQUENCY DRIVE, MODEL: TEST-VFD-075, rated output power: 75 kW, for industrial motor speed control',
    'dc-ac-inverter': 'DC to AC INVERTER, 12 VDC input, 230 VAC output, standalone power conversion device',
    'rectifier': 'RECTIFIER, standalone industrial AC to DC converter, not a battery charger, not for computers or telecommunications',
    'crochet-machine': 'COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW\n230011002000MM',
    'crochet-trimming': 'CROCHET MACHINE producing ornamental braid and trimming, electric motor power 1.5 kW',
    'flat-knitting': 'COMPUTERIZED FLAT KNITTING MACHINE, electric motor power 1.5 kW',
    'crochet-unknown-drive': 'CROCHET MACHINE producing ornamental braid and trimming',
    'circular-knitting': 'CIRCULAR KNITTING MACHINE, cylinder diameter: 200 mm, electric motor power: 1.5 kW',
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('samples', nargs='*')
parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1] / '.logs')
args = parser.parse_args()
unknown = set(args.samples) - samples.keys()
if unknown: parser.error(f'Unknown samples: {", ".join(sorted(unknown))}')
args.output_dir.mkdir(parents=True, exist_ok=True)
token = os.environ.get('HS_AUTH_TOKEN')
if not token:
    parser.error('Set HS_AUTH_TOKEN to a company account access token before running this check')
with httpx.Client(timeout=240, headers={'Authorization': f'Bearer {token}'}) as client:
    for name, description in samples.items():
        if args.samples and name not in args.samples: continue
        response = client.post('http://127.0.0.1:3001/api/classification/search', json={'description': description})
        response.raise_for_status()
        result = response.json()
        target = args.output_dir / f'{name}-result.json'
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        analysis = result.get('legalAnalysis') or {}
        assert analysis.get('summary') and analysis.get('conclusion'), name
        assert analysis.get('legal_steps') and analysis.get('references'), f'{name}: no verified legal analysis'
        saved = client.get(f'http://127.0.0.1:3001/api/classification/{result["id"]}')
        saved.raise_for_status()
        assert saved.json()['legalAnalysis'] == analysis, 'Legal explanation was not persisted'
        if name == 'fried-rice':
            assert result['status'] == 'CONDITIONAL'
            assert result['normalizedProduct'].get('declared_composition_percent') == 90
            assert len(analysis.get('hypotheses', [])) >= 2, 'Missing competing food hypotheses'
        if name == 'tv-console':
            # A model may explicitly assume ordinary use and return CONDITIONAL.
            # Verify the selected code in either valid output shape.
            assert result['status'] in ('COMPLETED', 'CONDITIONAL')
            selected_code = result['results'][0]['hsCode'] if result['status'] == 'COMPLETED' else result['normalizedProduct'].get('provisional_code')
            assert selected_code == '94036090'
            if result['status'] == 'CONDITIONAL':
                assert analysis.get('hypotheses') and all(h['code'] == '94036090' and h['assumptions'] and h['source_chunk_ids'] for h in analysis['hypotheses'])
            assert 'declared_composition_percent' not in result['normalizedProduct']
        if name == 'reversible-jacket':
            assert 'declared_composition_percent' not in result['normalizedProduct']
            assert not any('200%' in item for item in result.get('missingInformation', []))
        if name == 'gift-set':
            assert result['status'] == 'CONDITIONAL'
            assert len(analysis.get('decision_questions', [])) >= 3
            assert len(analysis.get('hypotheses', [])) >= 4
            assert not any(word in (analysis['summary'] + analysis['conclusion']).lower() for word in ('chưa đủ', 'chưa thể xác định'))
            assert any(h.get('classification_mode') == 'separate' and len(h.get('items', [])) >= 2 for h in analysis['hypotheses'])
            single = [h for h in analysis['hypotheses'] if h.get('classification_mode') == 'single']
            assert any(h['code'].startswith('621520') and '3(c)' in h['reasoning'] for h in single), 'Missing polyester/equal-character scenario'
            assert any(h['code'].startswith('621510') for h in single), 'Missing silk scenario'
            assert any(h['code'].startswith('611595') for h in single), 'Missing cotton-socks scenario'
            first = analysis['hypotheses'][0]
            if first['code'].startswith('6215'): assert first['code'].endswith('90'), 'Unrequested batik must not be the default'
        if name == 'servo-motor':
            assert result['status'] == 'CONDITIONAL', 'Undeclared power must not be marked as confirmed'
            hypotheses = analysis.get('hypotheses', [])
            assert len(hypotheses) >= 3, 'Missing competing national power ranges'
            assert {'85015229', '85015239', '85015390'} <= {h['code'] for h in hypotheses}, 'Relevant industrial power branches were omitted'
            assert len(analysis.get('decision_questions', [])) >= 3
            assert result['normalizedProduct'].get('provisional_code')
            assert not any(word in (analysis['summary'] + analysis['conclusion']).lower() for word in ('chưa đủ', 'chưa thể xác định'))
        if name == 'pneumatic-valve':
            assert result['status'] == 'CONDITIONAL'
            assert result['normalizedProduct'].get('provisional_code') == '84812090'
            hypotheses = analysis.get('hypotheses', [])
            assert {'84812090', '84812011', '84812019'} <= {h['code'] for h in hypotheses}
            assert hypotheses[0]['code'] == '84812090'
            assert len(analysis.get('decision_questions', [])) >= 3
            assert any('8481.20' in ref.get('excerpt', '') or '84.81' in ref.get('excerpt', '') for ref in analysis['references'])
        if name in ('inverter', 'frequency-converter', 'dc-ac-inverter', 'rectifier'):
            expected = {'inverter': '85044090', 'frequency-converter': '85044090', 'dc-ac-inverter': '85044040', 'rectifier': '85044030'}[name]
            assert result['normalizedProduct'].get('provisional_code') == expected
            assert result['status'] == 'CONDITIONAL'
            assert all(h['code'].startswith('850440') for h in analysis.get('hypotheses', []))
            assert len(analysis.get('decision_questions', [])) >= 3
            assert any('Thiết bị biến đổi dòng điện và tần số' in ref.get('excerpt', '') or '(II) CÁC THIẾT BỊ BIẾN ĐỔI TĨNH ĐIỆN' in ref.get('excerpt', '') for ref in analysis['references'])
        if name in ('crochet-machine', 'crochet-trimming', 'flat-knitting', 'crochet-unknown-drive', 'circular-knitting'):
            expected = {'crochet-machine': '84479010', 'crochet-trimming': '84479010', 'flat-knitting': '84472010', 'crochet-unknown-drive': '84479010', 'circular-knitting': '84471200'}[name]
            hypotheses = analysis.get('hypotheses', [])
            understanding = analysis.get('product_understanding') or {}
            assert understanding.get('meaning') and understanding.get('definition_source_ids'), 'Missing grounded product meaning'
            assert 'identity' not in understanding.get('missing_attributes', [])
            assert 'mechanism' not in understanding.get('missing_attributes', [])
            assert len(analysis.get('decision_questions', [])) >= 3
            if name == 'crochet-machine':
                assert any('máy dệt móc' in ref.get('excerpt', '').lower() for ref in analysis['references'])
                assert 'power' not in understanding.get('missing_attributes', [])
            if name == 'crochet-unknown-drive':
                assert result['status'] == 'CONDITIONAL'
                assert result['normalizedProduct'].get('provisional_code') == expected
                assert {h['code'] for h in hypotheses} == {'84479010', '84479020'}
                assert understanding.get('missing_attributes') == ['drive']
            else:
                assert result['status'] == 'COMPLETED', 'Declared machine type and drive must not become hypothetical'
                assert result['results'][0]['hsCode'] == expected
                assert not hypotheses, 'Do not add another identity just to produce alternatives'
                assert not understanding.get('missing_attributes')
        print(json.dumps({'sample': name, 'id': result['id'], 'status': result['status'],
                          'legal_steps': len(analysis.get('legal_steps', [])),
                          'references': len(analysis.get('references', [])),
                          'codes': [row['hsCode'] for row in result.get('results', [])],
                          'hypotheses': [row['code'] for row in analysis.get('hypotheses', [])],
                          'persisted': True}), flush=True)
