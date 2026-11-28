package main

import (
	"net/http"

	"rf4server/internal/panelui"
)

// 面板语言判定与页面壳渲染在 internal/panelui：cmd/launcher 整包依赖
// golang.org/x/sys/windows，Linux 上编译不了，函数留在本包里就没有可跑的测试。
// 这里只保留同名转发，main.go 的调用点不动。

const panelLangCookieMaxAge = panelui.CookieMaxAge

func panelIsLang(v string) bool { return panelui.IsLang(v) }

func panelLangFromRequest(r *http.Request) (string, bool) { return panelui.LangFromRequest(r) }

func panelLangSwitchHTML(lang string) string { return panelui.LangSwitchHTML(lang) }

func renderPanel(raw []byte, lang string) []byte { return panelui.RenderPanel(raw, lang) }
