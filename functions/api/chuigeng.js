/**
 * 吹更计数器 API
 * Cloudflare Pages Functions
 * GET  /api/chuigeng  → 读取数据
 * POST /api/chuigeng  → 吹更 +1
 */

const REPO   = "xiaxia5201314/mzzxy";
const PATH   = "chuigeng.json";
const BRANCH = "main";

// 从 GitHub 读取数据
async function readData(token) {
  const resp = await fetch(
    `https://api.github.com/repos/${REPO}/contents/${PATH}?ref=${BRANCH}`,
    { headers: { Authorization: `token ${token}`, "User-Agent": "mzzxy-pages" } }
  );
  if (!resp.ok) throw new Error("读取 GitHub 文件失败: " + resp.status);
  const file = await resp.json();
  const content = JSON.parse(atob(file.content.replace(/\n/g, "")));
  return { data: content, sha: file.sha };
}

// 写入数据到 GitHub
async function writeData(token, data, sha) {
  const body = {
    message: "chore: 吹更计数器更新",
    content: btoa(unescape(encodeURIComponent(JSON.stringify(data, null, 2)))),
    sha,
    branch: BRANCH,
  };
  const resp = await fetch(
    `https://api.github.com/repos/${REPO}/contents/${PATH}`,
    {
      method: "PUT",
      headers: {
        Authorization: `token ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "mzzxy-pages",
      },
      body: JSON.stringify(body),
    }
  );
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error("写入 GitHub 失败: " + resp.status + " " + err);
  }
}

// 获取 B站最新视频标题和 BV 号
async function fetchLatestVideo() {
  // 策略1: 搜索 API（无需登录）
  try {
    const url = `https://api.bilibili.com/x/web-interface/wbi/search/type?keyword=mid:93851573&search_type=video&order_type=pubdate&page=1`;
    const resp = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com"
      }
    });
    const data = await resp.json();
    if (data.code === 0) {
      const results = data.data?.result || [];
      if (results.length > 0) {
        return {
          bvid: results[0].bvid || "",
          title: results[0].title?.replace(/<[^>]+>/g, "") || "未知视频",
          aid: results[0].aid || 0,
        };
      }
    }
  } catch (e) {
    console.warn("搜索 API 失败:", e.message);
  }

  // 策略2: 空间投稿 API
  try {
    const url = `https://api.bilibili.com/x/space/arc/search?mid=93851573&ps=1&pn=1&order=pubdate`;
    const resp = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com"
      }
    });
    const data = await resp.json();
    if (data.code === 0) {
      const vlist = data.data?.list?.vlist || [];
      if (vlist.length > 0) {
        return {
          bvid: vlist[0].bvid || "",
          title: vlist[0].title || "未知视频",
          aid: vlist[0].aid || 0,
        };
      }
    }
  } catch (e) {
    console.warn("空间 API 失败:", e.message);
  }

  return null;
}

// GET：读取数据 + 检测新视频
export async function onRequestGet(context) {
  const token = context.env.GITHUB_TOKEN;
  if (!token) {
    return new Response(JSON.stringify({ error: "缺少 GITHUB_TOKEN" }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  try {
    const { data, sha } = await readData(token);

    // 检测新视频（异步，不阻塞返回）
    fetchLatestVideo().then(video => {
      if (video && video.bvid && video.bvid !== data.latest_video?.bvid) {
        // 新视频！清零并写入
        const newData = {
          ...data,
          total: 0,
          latest_video: {
            bvid: video.bvid,
            title: video.title,
            aid: video.aid,
          },
          last_update: formatBeijingTime(),
        };
        writeData(token, newData, sha).catch(e => console.error("检测新视频写入失败:", e));
      }
    }).catch(e => console.warn("检测新视频失败:", e));

    // 北京时间
    if (data.last_update) {
      data.last_update = data.last_update;
    }

    return new Response(JSON.stringify(data), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache",
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }
}

// POST：吹更 +1
export async function onRequestPost(context) {
  const token = context.env.GITHUB_TOKEN;
  if (!token) {
    return new Response(JSON.stringify({ error: "缺少 GITHUB_TOKEN" }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  try {
    const { data, sha } = await readData(token);

    // +1
    data.total = (data.total || 0) + 1;
    data.last_update = formatBeijingTime();

    await writeData(token, data, sha);

    return new Response(JSON.stringify(data), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }
}

// 北京时间格式化
function formatBeijingTime() {
  const now = new Date(Date.now() + 8 * 3600 * 1000);
  return now.toISOString().slice(0, 19).replace("T", " ");
}
