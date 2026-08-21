// module-level constant - excluded with functions-only
const char *MODULE_STR = "module_string";
int MODULE_NUM = 200;

void myFunc() {
    const char *x = "func_string";
    int n = 77;
}

void anotherFunc(const char *param) {
    const char *msg = "another_func";
}
