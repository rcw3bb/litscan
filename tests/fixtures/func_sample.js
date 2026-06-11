// module level - excluded with functions-only
const MODULE_STR = "module_string";
const MODULE_NUM = 200;

// Regular function
function myFunc() {
    const x = "func_string";
    const n = 99;
    return x;
}

// Arrow function
const arrowFn = (param) => {
    const msg = "arrow_string";
    return msg;
};

// Nested control flow inside function (literals still included)
function withControl() {
    if (true) {
        const inside = "control_inside";
    }
}
