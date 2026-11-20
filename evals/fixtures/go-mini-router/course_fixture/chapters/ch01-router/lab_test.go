package router_test

import (
	"net/http"
	"testing"

	student "example.com/go-mini-router/.promentor/chapters/ch01-router"
)

func guardPanic(t *testing.T) {
	t.Helper()
	if r := recover(); r != nil {
		t.Fatalf("unimplemented or panic: %v", r)
	}
}

// Part A: 基础行为
func TestPartA_StaticRoute(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	var called bool
	r.AddRoute("GET", "/users", func(w http.ResponseWriter, req *http.Request, params map[string]string) {
		called = true
	})
	h, params := r.FindRoute("GET", "/users")
	if h == nil {
		t.Fatal("GET /users: expected handler, got nil")
	}
	h(nil, nil, params)
	if !called {
		t.Fatal("GET /users: handler was not invoked")
	}
}

func TestPartA_ParamRoute(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	r.AddRoute("GET", "/users/:id", func(w http.ResponseWriter, req *http.Request, params map[string]string) {})
	h, params := r.FindRoute("GET", "/users/42")
	if h == nil {
		t.Fatal("GET /users/42: expected handler, got nil")
	}
	if params["id"] != "42" {
		t.Fatalf("expected id=42, got %q", params["id"])
	}
}

// Part B: 边界与异常
func TestPartB_MethodMismatchAndNotFound(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	r.AddRoute("GET", "/users", func(w http.ResponseWriter, req *http.Request, params map[string]string) {})
	if h, _ := r.FindRoute("POST", "/users"); h != nil {
		t.Fatal("POST /users: expected nil handler on method mismatch")
	}
	if h, _ := r.FindRoute("GET", "/unknown"); h != nil {
		t.Fatal("GET /unknown: expected nil handler on missing path")
	}
}

// Part C: 优先级与嵌套参数
func TestPartC_StaticPriorityAndNestedParams(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	var tag string
	r.AddRoute("GET", "/users/:id", func(w http.ResponseWriter, req *http.Request, params map[string]string) {
		tag = "param:" + params["id"]
	})
	r.AddRoute("GET", "/users/me", func(w http.ResponseWriter, req *http.Request, params map[string]string) {
		tag = "static"
	})
	r.AddRoute("GET", "/users/:uid/posts/:pid", func(w http.ResponseWriter, req *http.Request, params map[string]string) {
		tag = params["uid"] + ":" + params["pid"]
	})

	h, params := r.FindRoute("GET", "/users/me")
	if h == nil {
		t.Fatal("GET /users/me: expected handler")
	}
	h(nil, nil, params)
	if tag != "static" {
		t.Fatalf("expected static priority, got %q", tag)
	}

	h2, params2 := r.FindRoute("GET", "/users/7/posts/99")
	if h2 == nil {
		t.Fatal("GET /users/7/posts/99: expected handler")
	}
	h2(nil, nil, params2)
	if tag != "7:99" {
		t.Fatalf("expected 7:99, got %q", tag)
	}
}
