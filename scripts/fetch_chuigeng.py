#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美滋滋小院 - 吹更计数器爬虫
从 B 站用户 93851573 的最新视频评论区统计"吹更"评论数量

运行方式:
  python fetch_chuigeng.py                    # 自动获取最新视频
  python fetch_chuigeng.py BV1xx411x7xx       # 手动指定 BV 号
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ========== 配置 ==========
BILI_UID = 93851573
COMMENT_KEYWORD = "吹更"

# 多种 RSS 源备份
RSS_SOURCES = [
    f"https://rsshub.app/bilibili/user/video/{BILI_UID}",
    f"https://feed.miczeng.com/bilibili/user/video/{BILI_UID}",
    f"https://rss.shab.fun/bilibili/user/video/{BILI_UID}",
]

OUTPUT_FILE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "chuigeng.json"
))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

# ========== HTTP 工具 ==========

def http_get(url, timeout=12, as_json=True):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if as_json else raw
    except Exception:
        raise


# ========== 获取最新视频 BV 号 ==========

def get_bvid_from_rss():
    """通过 RSS 获取最新视频 BV 号"""
    for rss_url in RSS_SOURCES:
        try:
            xml_text = http_get(rss_url, as_json=False)
            root = ET.fromstring(xml_text)
            # 兼容 RSS 2.0 和 Atom 格式
            items = (root.findall(".//item") or
                     root.findall(".//{http://www.w3.org/2005/Atom}entry"))
            if items:
                item = items[0]
                link_el = item.find("link")
                title_el = item.find("title")
                link = (link_el.text or link_el.get("href", "")
                         if link_el is not None else "")
                title = title_el.text if title_el is not None else ""
                bv_match = re.search(r"(BV[a-zA-Z0-9]{10})", link)
                if bv_match and title and len(title) > 3 and "是什么意思" not in title:
                    print(f"  ✓ RSS 成功 ({rss_url[:40]}...)")
                    print(f"  标题: {title}")
                    return bv_match.group(1), title
        except Exception as e:
            print(f"  ✗ RSS {rss_url[:50]}: {e}")
            continue
    return None, None


def get_bvid_from_search_api():
    """通过 B 站搜索 API 获取最新视频"""
    try:
        url = (f"https://api.bilibili.com/x/web-interface/wbi/search/type"
                f"?keyword=mid:{BILI_UID}&search_type=video&order_type=pubdate&page=1")
        data = http_get(url)
        if data.get("code") == 0:
            results = data.get("data", {}).get("result", [])
            if results:
                bvid = results[0].get("bvid", "")
                title = results[0].get("title", "")
                # 去除标题中的 HTML 标签
                title = re.sub(r"<[^>]+>", "", title)
                if bvid and title and len(title) > 3 and "是什么意思" not in title:
                    print(f"  ✓ 搜索 API 成功")
                    print(f"  标题: {title}")
                    return bvid, title
    except Exception as e:
        print(f"  ✗ 搜索 API: {e}")
    return None, None


def get_bvid_from_space_api():
    """通过空间投稿 API（带简单签名）获取"""
    try:
        # 尝试不带 wbi 签名的空间投稿接口
        url = (f"https://api.bilibili.com/x/space/arc/search"
                f"?mid={BILI_UID}&ps=1&pn=1&order=pubdate")
        data = http_get(url)
        if data.get("code") == 0:
            vlist = data.get("data", {}).get("list", {}).get("vlist", [])
            if vlist:
                bvid = vlist[0].get("bvid", "")
                title = vlist[0].get("title", "")
                if bvid and title and len(title) > 3 and "是什么意思" not in title:
                    print(f"  ✓ 空间 API 成功")
                    print(f"  标题: {title}")
                    return bvid, title
    except Exception as e:
        print(f"  ✗ 空间 API: {e}")
    return None, None


def get_latest_bvid():
    """多策略获取最新视频，全部失败则使用缓存"""
    print("\n[1/3] 获取最新视频 BV 号...")
    print("  策略1: RSSHub...")
    bvid, title = get_bvid_from_rss()
    if bvid:
        return bvid, title

    print("  策略2: 搜索 API...")
    bvid, title = get_bvid_from_search_api()
    if bvid:
        return bvid, title

    print("  策略3: 空间投稿 API...")
    bvid, title = get_bvid_from_space_api()
    if bvid:
        return bvid, title

    # 降级：读取缓存
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                bvid = cache.get("latest_video", {}).get("bvid", "")
                title = cache.get("latest_video", {}).get("title", "")
                if bvid:
                    print(f"  ⚠ 使用缓存 BV 号: {bvid}")
                    print(f"  ⚠ 请尽快推送至 GitHub 让 Actions 自动更新")
                    return bvid, title
        except Exception:
            pass

    raise Exception("所有策略均失败，无法获取最新视频 BV 号")


# ========== 评论采集 ==========

def bvid_to_aid(bvid):
    """BV 号转 AV 号"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    data = http_get(url)
    if data.get("code") != 0:
        raise Exception(f"获取视频信息失败: {data.get('message', '未知错误')}")
    return data["data"]["aid"], data["data"]["title"]


def fetch_page_comments(aid, next_page, mode=3):
    """获取一页评论"""
    url = (f"https://api.bilibili.com/x/v2/reply/main"
           f"?type=1&oid={aid}&next={next_page}&mode={mode}")
    try:
        return http_get(url)
    except Exception as e:
        print(f"    ✗ 第 {next_page} 页失败: {e}")
        return None


def fetch_reply_page(aid, root, pn):
    """获取子回复一页"""
    url = (f"https://api.bilibili.com/x/v2/reply/reply"
           f"?type=1&oid={aid}&root={root}&pn={pn}&mode=3")
    try:
        return http_get(url)
    except Exception:
        return None


def count_comments_keyword(aid, keyword):
    """遍历所有评论，统计包含 keyword 的数量"""
    count = 0
    page = 1
    max_pages = 20  # 最多翻 20 页评论

    while page <= max_pages:
        data = fetch_page_comments(aid, page)
        if data is None:
            break

        d = data.get("data") or {}
        replies = d.get("replies") or []
        if not replies:
            break

        for comment in replies:
            # B站评论content是对象，文字在message字段
            content = comment.get("content", {})
            msg = content.get("message", "") if isinstance(content, dict) else str(content)
            if keyword in msg:
                count += 1
            # 子回复
            rcount = comment.get("rcount", 0)
            if rcount > 0:
                count += _count_replies(aid, comment["rpid"], keyword)

        cursor = d.get("cursor") or {}
        if cursor.get("is_end"):
            break
        page += 1
        time.sleep(0.35)

    return count


def _count_replies(aid, root, keyword, pn=1):
    """递归统计子回复中的关键词"""
    if pn > 5:  # 子回复最多 5 页
        return 0
    data = fetch_reply_page(aid, root, pn)
    if data is None:
        return 0
    d = data.get("data") or {}
    replies = d.get("replies") or []
    if not replies:
        return 0
    count = 0
    for r in replies:
        c = r.get("content", {})
        msg = c.get("message", "") if isinstance(c, dict) else str(c)
        if keyword in msg:
            count += 1
    # 继续翻页
    page_count = d.get("page", {}).get("acount", 0)
    if page_count > pn * 20:
        time.sleep(0.3)
        count += _count_replies(aid, root, keyword, pn + 1)
    return count


# ========== 主流程 ==========

def main():
    # 支持手动传入 BV 号
    manual_bvid = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 52)
    print("   美滋滋小院 · 吹更计数器")
    print("=" * 52)

    # 1. 获取 BV 号
    if manual_bvid:
        bvid = manual_bvid
        print(f"\n[手动模式] BV 号: {bvid}")
        aid, title = bvid_to_aid(bvid)
    else:
        bvid, title = get_latest_bvid()
        print(f"  ✓ BV 号: {bvid}")
        aid, _ = bvid_to_aid(bvid)
        title = _ or title

    print(f"  视频: {title}")
    print(f"  AID: {aid}")

    # 2. 读取历史数据
    old_total = 0
    old_bvid = ""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
                old_total = old.get("total", 0)
                old_bvid = old.get("latest_video", {}).get("bvid", "")
        except Exception:
            pass

    # 3. 统计评论
    if bvid == old_bvid and old_total > 0 and not manual_bvid:
        print(f"\n[2/3] 视频未更新，使用历史数据")
        total = old_total
        print(f"  累计吹更数: {total}")
    else:
        if bvid != old_bvid:
            print(f"\n[2/3] ⚡ 检测到新视频!")
            print(f"  旧: {old_bvid} → 新: {bvid}")
        print(f"\n[2/3] 爬取评论，统计「{COMMENT_KEYWORD}」...")
        new_count = count_comments_keyword(aid, COMMENT_KEYWORD)
        total = new_count
        print(f"  统计结果: {new_count}")

    # 4. 写入 JSON（北京时间 UTC+8）
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "total": total,
        "latest_video": {
            "bvid": bvid,
            "title": title,
            "aid": aid
        },
        "last_update": now,
        "keyword": COMMENT_KEYWORD
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 52}")
    print(f"  ✓ 完成! 累计吹更数: {total}")
    print(f"  ✓ 数据文件: {OUTPUT_FILE}")
    print(f"  ✓ 更新时间: {now}")
    print(f"{'=' * 52}")

    # GitHub Actions 输出
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"total={total}\n")
            f.write(f"last_update={now}\n")


if __name__ == "__main__":
    main()
