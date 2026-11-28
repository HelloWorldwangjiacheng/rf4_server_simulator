package panelui

import (
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
)

// 9500 控制面板的语言口径：?lang= > cookie lang > Accept-Language > 默认 zh。
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
		{"cookie 与 Accept-Language 同时存在时 cookie 优先", "/", "zh", "en-US,en;q=0.9", "zh", false},
		{"Accept-Language 取 en", "/", "", "en-US,en;q=0.9,zh-CN;q=0.8", "en", false},
		{"Accept-Language 取 zh", "/", "", "zh-CN,zh;q=0.9,en;q=0.8", "zh", false},
		{"无法识别时默认 zh", "/", "", "fr-FR,de;q=0.8", "zh", false},
		{"什么都没带默认 zh", "/", "", "", "zh", false},
		{"带空段的 Accept-Language", "/", "", ",,en-GB;q=0.5", "en", false},
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
			lang, fromQuery := LangFromRequest(r)
			if lang != c.wantLang || fromQuery != c.wantFromQuery {
				t.Fatalf("lang=%q fromQuery=%v，期望 %q %v", lang, fromQuery, c.wantLang, c.wantFromQuery)
			}
		})
	}
}

// 一年 31536000 秒：cookie 参数与 8080 侧同值。
func TestCookieMaxAge(t *testing.T) {
	if CookieMaxAge != 31536000 {
		t.Fatalf("CookieMaxAge=%d，期望 31536000", CookieMaxAge)
	}
}

var cjkRE = regexp.MustCompile(`[\x{3000}-\x{303f}\x{3400}-\x{4dbf}\x{4e00}-\x{9fff}\x{f900}-\x{faff}\x{ff00}-\x{ffef}]`)

// 切换控件：en 页 aria-label 与可见文字都不含 CJK；zh 页与抽取前逐字一致。
func TestLangSwitchHTML(t *testing.T) {
	en := LangSwitchHTML("en")
	if cjkRE.MatchString(en) {
		t.Fatalf("en 切换控件仍含 CJK：%s", en)
	}
	for _, want := range []string{`aria-label="Language"`, `>ZH</a>`, `>EN</a>`, `aria-current="true"`} {
		if !strings.Contains(en, want) {
			t.Fatalf("en 切换控件缺少 %q：%s", want, en)
		}
	}
	zh := LangSwitchHTML("zh")
	wantZh := `<nav id="lang-switch" class="lang-switch" aria-label="语言 / Language">` +
		`<a href="?lang=zh" hreflang="zh" aria-current="true">中文</a>` +
		`<a href="?lang=en" hreflang="en">EN</a></nav>`
	if zh != wantZh {
		t.Fatalf("zh 切换控件与抽取前不一致：\n got %s\nwant %s", zh, wantZh)
	}
}

func TestIsLang(t *testing.T) {
	for _, v := range []string{"zh", "en"} {
		if !IsLang(v) {
			t.Fatalf("IsLang(%q) 应为 true", v)
		}
	}
	for _, v := range []string{"", "ZH", "en-US", "fr"} {
		if IsLang(v) {
			t.Fatalf("IsLang(%q) 应为 false", v)
		}
	}
}

const panelFixture = "<!doctype html>\n" +
	"<html lang=\"zh-CN\">\n" +
	"<head>\n" +
	"<meta charset=\"utf-8\">\n" +
	"<title>RF4 本地服务器</title>\n" +
	"<script>window.RF4_LANG=\"zh\";</script>\n" +
	"</head>\n" +
	"<body>\n" +
	"<nav id=\"lang-switch\" class=\"lang-switch\"></nav>\n" +
	"<p>游戏逻辑</p>\n" +
	"</body>\n" +
	"</html>\n"

// extractAttrs 取 title 文本与 title/placeholder/aria-label/alt 属性值：这些是「用户看得见的字」。
func extractAttrs(t *testing.T, s string) []string {
	t.Helper()
	out := []string{}
	if m := regexp.MustCompile(`(?s)<title>(.*?)</title>`).FindStringSubmatch(s); m != nil {
		out = append(out, m[1])
	}
	attr := regexp.MustCompile(`(?:title|placeholder|aria-label|alt)="([^"]*)"`)
	for _, m := range attr.FindAllStringSubmatch(s, -1) {
		out = append(out, m[1])
	}
	if i := strings.Index(s, `<nav id="lang-switch"`); i >= 0 {
		block := s[i:]
		if j := strings.Index(block, "</nav>"); j >= 0 {
			block = block[:j]
			block = regexp.MustCompile(`<[^>]*>`).ReplaceAllString(block, " ")
			out = append(out, block)
		}
	}
	return out
}

// en 页面壳：title / aria-label / 切换控件文字零 CJK，window.RF4_LANG 与 <html lang> 切到 en。
func TestRenderPanelEnglish(t *testing.T) {
	got := string(RenderPanel([]byte(panelFixture), "en"))
	for _, want := range []string{
		`<html lang="en">`,
		`<title>RF4 Local Server</title>`,
		`window.RF4_LANG="en";`,
		`aria-label="Language"`,
	} {
		if !strings.Contains(got, want) {
			t.Fatalf("en 页面壳缺少 %q：%s", want, got)
		}
	}
	if strings.Contains(got, `aria-current="true">中文`) {
		t.Fatalf("en 页面壳仍把中文标成当前语言：%s", got)
	}
	for _, v := range extractAttrs(t, got) {
		if cjkRE.MatchString(v) {
			t.Fatalf("en 页面壳用户可见文字仍含 CJK：%q（整页 %s）", v, got)
		}
	}
}

// zh 页面壳：与抽取前逐字节相同（只有原本的空 <nav> 被填成 zh 控件）。
func TestRenderPanelChineseUnchanged(t *testing.T) {
	want := strings.Replace(panelFixture,
		`<nav id="lang-switch" class="lang-switch"></nav>`,
		`<nav id="lang-switch" class="lang-switch" aria-label="语言 / Language">`+
			`<a href="?lang=zh" hreflang="zh" aria-current="true">中文</a>`+
			`<a href="?lang=en" hreflang="en">EN</a></nav>`, 1)
	got := string(RenderPanel([]byte(panelFixture), "zh"))
	if got != want {
		t.Fatalf("zh 页面壳与修复前不一致：\n got %q\nwant %q", got, want)
	}
}

// 找不到标记时原样返回，不 panic、不猜。
func TestRenderPanelMissingMarkersIsNoop(t *testing.T) {
	raw := []byte("<html><body>裸页面</body></html>")
	if got := string(RenderPanel(raw, "en")); got != string(raw) {
		t.Fatalf("缺标记时应原样返回，got %q", got)
	}
}
