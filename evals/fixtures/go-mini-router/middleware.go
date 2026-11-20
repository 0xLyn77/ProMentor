package minirouter

import "net/http"

// Middleware wraps a Handler with cross-cutting behavior.
type Middleware func(Handler) Handler

// Chain composes middlewares from outermost to innermost.
func Chain(final Handler, middlewares ...Middleware) Handler {
	wrapped := final
	for i := len(middlewares) - 1; i >= 0; i-- {
		wrapped = middlewares[i](wrapped)
	}
	return wrapped
}

// ServeHTTP adapts Router to standard net/http requests.
func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	handler, params := r.FindRoute(req.Method, req.URL.Path)
	if handler == nil {
		http.NotFound(w, req)
		return
	}
	handler(w, req, params)
}
