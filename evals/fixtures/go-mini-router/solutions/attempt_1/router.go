package router

import (
	"net/http"
	"strings"
)

// Handler handles an HTTP request along with extracted path parameters.
type Handler func(w http.ResponseWriter, req *http.Request, params map[string]string)

type routeEntry struct {
	method   string
	segments []string
	handler  Handler
}

// Router (Attempt 1: linear rule list with static-count priority).
type Router struct {
	entries []routeEntry
}

func NewRouter() *Router {
	return &Router{}
}

func (r *Router) AddRoute(method, path string, handler Handler) {
	if method == "" || path == "" || handler == nil {
		return
	}
	r.entries = append(r.entries, routeEntry{
		method:   method,
		segments: splitPath(path),
		handler:  handler,
	})
}

func (r *Router) FindRoute(method, path string) (Handler, map[string]string) {
	reqSegs := splitPath(path)
	var bestHandler Handler
	var bestParams map[string]string
	bestStatic := -1

	for _, entry := range r.entries {
		if entry.method != method || len(entry.segments) != len(reqSegs) {
			continue
		}
		params := make(map[string]string)
		staticMatches := 0
		ok := true
		for i, pat := range entry.segments {
			if strings.HasPrefix(pat, ":") {
				params[strings.TrimPrefix(pat, ":")] = reqSegs[i]
			} else if pat == reqSegs[i] {
				staticMatches++
			} else {
				ok = false
				break
			}
		}
		if ok && staticMatches > bestStatic {
			bestStatic = staticMatches
			bestHandler = entry.handler
			bestParams = params
		}
	}
	return bestHandler, bestParams
}

func splitPath(path string) []string {
	trimmed := strings.Trim(path, "/")
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "/")
}
