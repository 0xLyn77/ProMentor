package minirouter

import (
	"net/http"
	"strings"
)

// Handler handles an HTTP request with extracted path parameters.
type Handler func(w http.ResponseWriter, req *http.Request, params map[string]string)

type node struct {
	segment  string
	isParam  bool
	paramKey string
	children []*node
	handler  Handler
}

// Router dispatches HTTP requests using a per-method segment trie.
type Router struct {
	trees map[string]*node
}

// NewRouter creates an empty Router.
func NewRouter() *Router {
	return &Router{trees: make(map[string]*node)}
}

// AddRoute registers a handler for an HTTP method and path pattern.
// Pattern segments starting with ":" capture dynamic path parameters.
func (r *Router) AddRoute(method, path string, handler Handler) {
	if method == "" || path == "" || handler == nil {
		return
	}
	root, ok := r.trees[method]
	if !ok {
		root = &node{segment: "/"}
		r.trees[method] = root
	}
	curr := root
	for _, seg := range splitSegments(path) {
		curr = curr.getOrCreateChild(seg)
	}
	curr.handler = handler
}

// FindRoute matches a request method and path, returning the handler and params.
// Static segments always take precedence over parameter segments.
func (r *Router) FindRoute(method, path string) (Handler, map[string]string) {
	root, ok := r.trees[method]
	if !ok {
		return nil, nil
	}
	params := make(map[string]string)
	matched := matchNode(root, splitSegments(path), 0, params)
	if matched == nil || matched.handler == nil {
		return nil, nil
	}
	return matched.handler, params
}

func (n *node) getOrCreateChild(seg string) *node {
	isParam := strings.HasPrefix(seg, ":")
	for _, child := range n.children {
		if child.segment == seg {
			return child
		}
	}
	child := &node{
		segment: seg,
		isParam: isParam,
	}
	if isParam {
		child.paramKey = strings.TrimPrefix(seg, ":")
	}
	n.children = append(n.children, child)
	return child
}

func matchNode(curr *node, segments []string, idx int, params map[string]string) *node {
	if idx == len(segments) {
		return curr
	}
	seg := segments[idx]
	// Pass 1: static segments take priority.
	for _, child := range curr.children {
		if !child.isParam && child.segment == seg {
			if found := matchNode(child, segments, idx+1, params); found != nil && found.handler != nil {
				return found
			}
		}
	}
	// Pass 2: fall back to parameter segments.
	for _, child := range curr.children {
		if child.isParam {
			params[child.paramKey] = seg
			if found := matchNode(child, segments, idx+1, params); found != nil && found.handler != nil {
				return found
			}
			delete(params, child.paramKey)
		}
	}
	return nil
}

func splitSegments(path string) []string {
	trimmed := strings.Trim(path, "/")
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "/")
}
