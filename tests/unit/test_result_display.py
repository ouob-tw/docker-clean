from docker_clean.engine import Image
from docker_clean.plan import Result, render_results


def test_results_group_receipts_under_image_name_and_summarize_targets():
    image = Image("sha256:" + "a" * 64, ("app:1", "alias:latest"), 1, "2026-01-01")
    receipts = ["Untagged: app:1", "Untagged: alias:latest", f"Deleted: {image.id}"]
    results = [Result("移除 tag", image.id, receipts[0]),
               Result("移除 tag", image.id, receipts[1]),
               Result("刪除 image", image.id, receipts[2]),
               Result("失敗", "sha256:" + "b" * 64, "conflict: image in use"),
               Result("跳過", "sha256:" + "c" * 64, "image／tag／容器引用已變更")]
    output = render_results(results, [image])
    assert "3 個目標｜完成 1｜跳過 1｜失敗 1" in output
    assert "1. app:1, alias:latest" in output
    assert output.count(image.id) == 1
    for receipt in receipts:
        assert output.count(receipt) == 1
    assert "conflict: image in use" in output
    assert "sha256:" + "b" * 64 in output
    assert "sha256:" + "c" * 64 in output
    assert render_results([]) == "沒有清理候選"


def test_legacy_tag_receipts_are_grouped_as_one_image():
    image = Image("sha256:" + "a" * 64, ("app:1", "app:2"), 1, "2026-01-01")
    results = [Result("移除 tag", "app:1", "Untagged: app:1"),
               Result("移除 tag", "app:2", "Untagged: app:2"),
               Result("刪除 image", "app:2", f"Deleted: {image.id}")]
    output = render_results(results, [image])
    assert "1 個目標｜完成 1" in output
    assert "app:1, app:2" in output
    assert output.count(image.id) == 1


def test_receipts_without_inventory_do_not_repeat_full_id_on_every_line():
    target = "sha256:" + "a" * 64
    results = [Result("移除 tag", target, "Untagged: app:1"),
               Result("刪除 image", target, f"Deleted: {target}")]
    assert render_results(results).count(target) == 1
