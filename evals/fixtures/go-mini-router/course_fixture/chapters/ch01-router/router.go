package router

import "net/http"

// Handler handles an HTTP request along with extracted path parameters.
type Handler func(w http.ResponseWriter, req *http.Request, params map[string]string)

// Router stores routes and matches incoming requests.
type Router struct {
	// TODO: 选择合适的数据结构存储路由表
}

// NewRouter creates a new empty Router.
func NewRouter() *Router {
	panic("not implemented: NewRouter")
}

// AddRoute registers a handler for the given HTTP method and path pattern.
func (r *Router) AddRoute(method, path string, handler Handler) {
	panic("not implemented: AddRoute")
}

// FindRoute finds the matching handler and extracts path parameters.
// Returns (nil, nil) when no route matches.
func (r *Router) FindRoute(method, path string) (Handler, map[string]string) {
	panic("not implemented: FindRoute")
}
