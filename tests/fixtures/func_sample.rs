// module-level constant - excluded with functions-only
static MODULE_STR: &str = "module_string";
static MODULE_NUM: i32 = 200;

fn my_func() -> &'static str {
    let x = "func_string";
    let n: i32 = 77;
    x
}

fn another_func(param: &str) {
    let msg = "another_func";
    println!("{}", msg);
}
