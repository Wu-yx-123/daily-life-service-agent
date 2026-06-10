# 作用：验证服务类型关键词匹配能兼容用户说法和门店服务命名差异。
from app.utils.service_match import matches_service_type


def test_service_type_should_match_real_store_aliases():
    assert matches_service_type("肩颈按摩", "肩颈舒缓 60 分钟 肩颈理疗 肩颈 久坐 放松")
    assert matches_service_type("做个脚部按摩", "足底反射 60 分钟 足疗 足底 反射区 循环")
    assert matches_service_type("想做拉伸", "运动拉伸 75 分钟 运动康复 拉伸 筋膜 运动恢复")


def test_spa_should_not_match_neck_service():
    assert not matches_service_type("精油SPA", "肩颈舒缓 60 分钟 肩颈理疗 肩颈 久坐 放松")
    assert matches_service_type("精油SPA", "精油 SPA 90 分钟 芳香 SPA 精油 舒压 轻柔")
