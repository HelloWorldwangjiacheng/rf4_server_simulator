package panelui

import (
	"net/http"
	"strings"
)

// 语言口径（9500 控制面板的 i18n）：?lang= 参数 > cookie lang > Accept-Language > 默认 zh。
// 与 8080 管理后台（internal/admin/lang_page.go）同一口径、同一个 cookie 名与参数，
// 所以同一台机器上两个端口的语言偏好是共用的（cookie Path=/，同源）。
//
// 这里只改「页面壳」：<html lang>、<title>、window.RF4_LANG、顶栏语言切换控件。
// 文案本身在 panel.html 的内嵌字典（生成物，源文件 tools/panel_en.py）。
//
// 为什么单独成包：cmd/launcher 整包 import golang.org/x/sys/windows，Linux 上编译不了，
// 于是包内的语言判定与页面壳渲染没有可跑的测试。这里不依赖 windows、不碰启动器其它逻辑，
// 只把「语言判定 + 页面壳渲染」抽出来，调用方（cmd/launcher/panel_lang.go）保留同名薄封装。

// CookieMaxAge 是一年，与简报标准 7 的口径一致。
const CookieMaxAge = 31536000

// IsLang 判断取值是否为受支持的语言。
func IsLang(v string) bool { return v == "zh" || v == "en" }

// LangFromRequest 返回本次请求生效的语言，以及是否来自 ?lang=（来自参数时要回写 cookie）。
func LangFromRequest(r *http.Request) (string, bool) {
	if v := r.URL.Query().Get("lang"); IsLang(v) {
		return v, true
	}
	if c, err := r.Cookie("lang"); err == nil && IsLang(c.Value) {
		return c.Value, false
	}
	for _, part := range strings.Split(r.Header.Get("Accept-Language"), ",") {
		tag := strings.ToLower(strings.TrimSpace(strings.SplitN(part, ";", 2)[0]))
		if tag == "" {
			continue
		}
		if strings.HasPrefix(tag, "en") {
			return "en", false
		}
		if strings.HasPrefix(tag, "zh") {
			return "zh", false
		}
	}
	return "zh", false
}

// LangSwitchHTML 生成语言切换控件。英文页不出现中文、中文页不出现英文译名，
// 保证「en 页文本节点零 CJK（含 aria-label）」与「中文页仍是中文」两条同时成立。
func LangSwitchHTML(lang string) string {
	if lang == "zh" {
		return `<nav id="lang-switch" class="lang-switch" aria-label="语言 / Language">` +
			`<a href="?lang=zh" hreflang="zh" aria-current="true">中文</a>` +
			`<a href="?lang=en" hreflang="en">EN</a></nav>`
	}
	return `<nav id="lang-switch" class="lang-switch" aria-label="Language">` +
		`<a href="?lang=zh" hreflang="zh">ZH</a>` +
		`<a href="?lang=en" hreflang="en" aria-current="true">EN</a></nav>`
}

// RenderPanel 把内嵌的 panel.html 按当前语言改写成页面壳。改的都是静态标记，
// 找不到标记时原样返回（不 panic、不猜）。
func RenderPanel(raw []byte, lang string) []byte {
	s := string(raw)
	htmlLang := "zh-CN"
	if lang == "en" {
		htmlLang = "en"
		s = strings.Replace(s, `<title>RF4 本地服务器</title>`, `<title>RF4 Local Server</title>`, 1)
		s = strings.Replace(s, `window.RF4_LANG="zh";`, `window.RF4_LANG="en";`, 1)
	}
	s = strings.Replace(s, `<html lang="zh-CN">`, `<html lang="`+htmlLang+`">`, 1)
	s = strings.Replace(s, `<nav id="lang-switch" class="lang-switch"></nav>`, LangSwitchHTML(lang), 1)
	return []byte(s)
}
