package router

import (
	"net/http"
	"strings"
)

// Handler handles an HTTP request along with extracted path parameters.
type Handler func(w http.ResponseWriter, req *http.Request, params map[string]string)

type trieNode struct {
	segment  string
	isParam  bool
	paramKey string
	children []*trieNode
	handler  Handler
}

// Router (Attempt 2: refactored to per-method segment trie).
type Router struct {
	roots map[string]*trieNode
}

func NewRouter() *Router {
	return &Router{roots: make(map[string]*trieNode)}
}

func (r *Router) AddRoute(method, path string, handler Handler) {
	if method == "" || path == "" || handler == nil {
		return
	}
	root, ok := r.roots[method]
	if !ok {
		root = &trieNode{segment: "/"}
		r.roots[method] = root
	}
	curr := root
	for _, seg := range splitPath(path) {
		curr = curr.childOrInsert(seg)
	}
	curr.handler = handler
}

func (r *Router) FindRoute(method, path string) (Handler, map[string]string) {
	root, ok := r.roots[method]
	if !ok {
		return nil, nil
	}
	params := make(map[string]string)
	matched := searchTrie(root, splitPath(path), 0, params)
	if matched == nil || matched.handler == nil {
		return nil, nil
	}
	return matched.handler, params
}

func (n *trieNode) childOrInsert(seg string) *trieNode {
	for _, c := range n.children {
		if c.segment == seg {
			return c
		}
	}
	isParam := strings.HasPrefix(seg, ":")
	child := &trieNode{segment: seg, isParam: isParam}
	if isParam {
		child.paramKey = strings.TrimPrefix(seg, ":")
	}
	n.children = append(n.children, child)
	return child
}

func searchTrie(curr *trieNode, segs []string, idx int, params map[string]string) *trieNode {
	if idx == len(segs) {
		return curr
	}
	seg := segs[idx]
	for _, c := range curr.children {
		if !c.isParam && c.segment == seg {
			if found := searchTrie(c, segs, idx+1, params); found != nil && found.handler != nil {
				return found
			}
		}
	}
	for _, c := range curr.children {
		if c.isParam {
			params[c.paramKey] = seg
			if found := searchTrie(c, segs, idx+1, params); found != nil && found.handler != nil {
				return found
			}
			delete(params, c.paramKey)
		}
	}
	return nil
}

func splitPath(path string) []string {
	trimmed := strings.Trim(path, "/")
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "/")
}
