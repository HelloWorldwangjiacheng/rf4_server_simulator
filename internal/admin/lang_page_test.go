package admin

import (
	"io/fs"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
)

var cjkRE = regexp.MustCompile(`[\x{3000}-\x{303f}\x{3400}-\x{4dbf}\x{4e00}-\x{9fff}\x{f900}-\x{faff}\x{ff00}-\x{ffef}]`)

// 语言口径：?lang= > cookie lang > Accept-Language > 默认 zh。
func TestLangFromRequestPrecedence(t *testing.T) {
	cases := []struct {
		name          string
		target        string
		cookie        string
		accept        string
		wantLang      string
		wantFromQuery bool
	}{
		{"query en 覆盖 cookie zh", "/?lang=en", "zh", "", "en", true},
		{"query zh 覆盖 cookie en", "/?lang=zh", "en", "", "zh", true},
		{"非法 query 落到 cookie", "/?lang=fr", "en", "", "en", false},
		{"无 query 用 cookie", "/", "en", "", "en", false},
		{"非法 cookie 被忽略", "/", "de", "", "zh", false},
		{"Accept-Language 取 en", "/", "", "en-US,en;q=0.9,zh-CN;q=0.8", "en", false},
		{"Accept-Language 取 zh", "/", "", "zh-CN,zh;q=0.9,en;q=0.8", "zh", false},
		{"无法识别时默认 zh", "/", "", "fr-FR,de;q=0.8", "zh", false},
		{"什么都没带默认 zh", "/", "", "", "zh", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := httptest.NewRequest(http.MethodGet, c.target, nil)
			if c.cookie != "" {
				r.AddCookie(&http.Cookie{Name: "lang", Value: c.cookie})
			}
			if c.accept != "" {
				r.Header.Set("Accept-Language", c.accept)
			}
			lang, fromQuery := langFromRequest(r)
			if lang != c.wantLang || fromQuery != c.wantFromQuery {
				t.Fatalf("lang=%q fromQuery=%v，期望 %q %v", lang, fromQuery, c.wantLang, c.wantFromQuery)
			}
		})
	}
}

func readIndexHTML(t *testing.T) []byte {
	t.Helper()
	raw, err := fs.ReadFile(WebFS(), "index.html")
	if err != nil {
		t.Fatalf("读内嵌 index.html 失败：%v", err)
	}
	return raw
}

func navBlock(t *testing.T, page string) string {
	t.Helper()
	start := strings.Index(page, `<nav id="lang-switch"`)
	if start < 0 {
		t.Fatal("页面壳里没有 lang-switch 控件")
	}
	end := strings.Index(page[start:], "</nav>")
	if end < 0 {
		t.Fatal("lang-switch 控件没有闭合")
	}
	return page[start : start+end+len("</nav>")]
}

// 页面壳按语言改写：<html lang>、<title>、window.__LANG__、切换控件。
func TestRenderIndexShellByLang(t *testing.T) {
	raw := readIndexHTML(t)

	zh := string(renderIndex(raw, "zh"))
	if !strings.Contains(zh, `<html lang="zh-CN">`) {
		t.Fatal("zh 页面壳应保留 <html lang=\"zh-CN\">")
	}
	if !strings.Contains(zh, `<title>RF4 管理后台</title>`) {
		t.Fatal("zh 页面壳的 title 不应被改写")
	}
	if !strings.Contains(zh, `window.__LANG__="zh";`) {
		t.Fatal("zh 页面壳缺少 window.__LANG__=\"zh\"")
	}
	zhNav := navBlock(t, zh)
	if !strings.Contains(zhNav, `aria-current="true">中文</a>`) {
		t.Fatalf("zh 切换控件应把中文标为当前语言，实际：%s", zhNav)
	}
	// zh 页的 aria-label 与修复前一致（中文页不出现英文译名以外的改动）。
	if !strings.Contains(zhNav, `aria-label="语言 / Language"`) {
		t.Fatalf("zh 切换控件的 aria-label 应与修复前一致，实际：%s", zhNav)
	}

	en := string(renderIndex(raw, "en"))
	if !strings.Contains(en, `<html lang="en">`) {
		t.Fatal("en 页面壳应把 <html lang> 改成 en")
	}
	if !strings.Contains(en, `<title>RF4 Admin Console</title>`) {
		t.Fatal("en 页面壳应把 title 换成英文")
	}
	if !strings.Contains(en, `window.__LANG__="en";`) {
		t.Fatal("en 页面壳缺少 window.__LANG__=\"en\"")
	}
	nav := navBlock(t, en)
	if !strings.Contains(nav, `aria-current="true">EN</a>`) {
		t.Fatalf("en 切换控件应把 EN 标为当前语言，实际：%s", nav)
	}
	if strings.Contains(nav, "中文") {
		t.Fatalf("en 切换控件不应出现中文，实际：%s", nav)
	}
	// 用户看得见的字里零 CJK：切换控件整体（含 aria-label）不允许中文。
	if !strings.Contains(nav, `aria-label="Language"`) {
		t.Fatalf("en 切换控件的 aria-label 应为英文，实际：%s", nav)
	}
	if cjkRE.MatchString(nav) {
		t.Fatalf("en 切换控件仍含 CJK，实际：%s", nav)
	}
	if cjkRE.MatchString(strings.SplitN(strings.SplitN(en, "<title>", 2)[1], "</title>", 2)[0]) {
		t.Fatalf("en 页面壳 title 仍含 CJK")
	}
	// window.__LANG__ 必须早于 main.js 执行。
	iLang := strings.Index(en, `window.__LANG__="en";`)
	iMain := strings.Index(en, `src="app/main.js"`)
	if iLang < 0 || iMain < 0 || iLang > iMain {
		t.Fatal("window.__LANG__ 未注入到 main.js 之前")
	}
}

// 找标记不到时原样返回，不改写、不 panic。
func TestRenderIndexWithoutMarkersReturnsRaw(t *testing.T) {
	raw := []byte("<p>no markers here</p>")
	if got := string(renderIndex(raw, "en")); got != string(raw) {
		t.Fatalf("无标记页面被改写：%q", got)
	}
}

// ?lang= 访问时回写 cookie，且页面壳与响应头随之切换。
func TestHandleIndexPageSetsCookieFromQuery(t *testing.T) {
	s := &Server{webFS: WebFS()}

	rec := httptest.NewRecorder()
	s.handleIndexPage(rec, httptest.NewRequest(http.MethodGet, "/?lang=en", nil))
	res := rec.Result()
	var langCookie *http.Cookie
	for _, c := range res.Cookies() {
		if c.Name == "lang" {
			langCookie = c
		}
	}
	if langCookie == nil {
		t.Fatal("?lang=en 未回写 cookie")
	}
	if langCookie.Value != "en" || langCookie.Path != "/" || langCookie.MaxAge != langCookieMaxAge || langCookie.SameSite != http.SameSiteLaxMode {
		t.Fatalf("cookie 参数不对：value=%q path=%q maxAge=%d sameSite=%d",
			langCookie.Value, langCookie.Path, langCookie.MaxAge, langCookie.SameSite)
	}
	if body := rec.Body.String(); !strings.Contains(body, `window.__LANG__="en";`) {
		t.Fatal("?lang=en 的响应体不是英文页面壳")
	}
	if vary := res.Header.Get("Vary"); !strings.Contains(vary, "Accept-Language") {
		t.Fatalf("Vary 头未覆盖 Accept-Language：%q", vary)
	}

	// 不带 ?lang= 时不应反复下发 cookie。
	rec2 := httptest.NewRecorder()
	s.handleIndexPage(rec2, httptest.NewRequest(http.MethodGet, "/", nil))
	for _, c := range rec2.Result().Cookies() {
		if c.Name == "lang" {
			t.Fatal("不带 ?lang= 的请求不应回写 cookie")
		}
	}
	if body := rec2.Body.String(); !strings.Contains(body, `window.__LANG__="zh";`) {
		t.Fatal("默认请求的页面壳应为 zh")
	}
}
