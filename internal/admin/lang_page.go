package admin

import (
	"io/fs"
	"net/http"
	"strings"
)

// 语言口径（i18n）：?lang= 参数 > cookie lang > Accept-Language > 默认 zh。
// cookie 名 lang，取值 zh|en，Path=/，Max-Age=31536000（一年）。
// 只影响页面壳（<html lang>、window.__LANG__、语言切换控件）；文案本身在前端字典里。

const langCookieMaxAge = 31536000 // 一年，按简报标准 7 的口径

func isLang(v string) bool { return v == "zh" || v == "en" }

// langFromRequest 返回本次请求生效的语言，以及是否来自 ?lang=（来自参数时要回写 cookie）。
func langFromRequest(r *http.Request) (string, bool) {
	if v := r.URL.Query().Get("lang"); isLang(v) {
		return v, true
	}
	if c, err := r.Cookie("lang"); err == nil && isLang(c.Value) {
		return c.Value, false
	}
	// Accept-Language: "en-US,en;q=0.9,zh-CN;q=0.8" → 按出现顺序取第一个可识别的。
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

// 切换控件：英文页不出现中文，中文页不出现英文别名，保证 en 页文本节点零 CJK。
func langSwitchHTML(lang string) string {
	zhAttr, enAttr := ` hreflang="zh"`, ` hreflang="en"`
	if lang == "zh" {
		return `<nav id="lang-switch" class="lang-switch" aria-label="语言 / Language">` +
			`<a href="?lang=zh"` + zhAttr + ` aria-current="true">中文</a>` +
			`<a href="?lang=en"` + enAttr + `>EN</a></nav>`
	}
	return `<nav id="lang-switch" class="lang-switch" aria-label="语言 / Language">` +
		`<a href="?lang=zh"` + zhAttr + `>ZH</a>` +
		`<a href="?lang=en"` + enAttr + ` aria-current="true">EN</a></nav>`
}

// renderIndex 把内嵌的 index.html 按当前语言改写成页面壳。
func renderIndex(raw []byte, lang string) []byte {
	s := string(raw)
	htmlLang := "zh-CN"
	if lang == "en" {
		htmlLang = "en"
	}
	head := `<script>window.__LANG__=` + `"` + lang + `";</script>`
	// 1) <html lang="zh-CN"> → 当前语言；<title> 跟着换（tab 标题也是用户看得到的字）
	s = strings.Replace(s, `<html lang="zh-CN">`, `<html lang="`+htmlLang+`">`, 1)
	if lang == "en" {
		s = strings.Replace(s, `<title>RF4 管理后台</title>`, `<title>RF4 Admin Console</title>`, 1)
	}
	// 2) 在模块入口前注入 window.__LANG__（必须早于 main.js 执行）
	s = strings.Replace(s, `<script type="module" src="app/main.js"></script>`, head+"\n"+`<script type="module" src="app/main.js"></script>`, 1)
	// 3) 切换控件插到 <body> 之后
	s = strings.Replace(s, "<body>", "<body>\n"+langSwitchHTML(lang), 1)
	return []byte(s)
}

// handleIndexPage 提供 / 与 /index.html 的页面壳；其余静态资源仍走 http.FileServer。
func (s *Server) handleIndexPage(w http.ResponseWriter, r *http.Request) {
	if s.webFS == nil {
		http.NotFound(w, r)
		return
	}
	raw, err := fs.ReadFile(s.webFS, "index.html")
	if err != nil {
		http.NotFound(w, r)
		return
	}
	lang, fromQuery := langFromRequest(r)
	if fromQuery {
		// 用 ?lang= 访问时把偏好写进 cookie，之后不带参数也是这个语言。
		http.SetCookie(w, &http.Cookie{
			Name:     "lang",
			Value:    lang,
			Path:     "/",
			MaxAge:   langCookieMaxAge,
			SameSite: http.SameSiteLaxMode,
		})
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Vary", "Cookie, Accept-Language")
	w.Write(renderIndex(raw, lang))
}
