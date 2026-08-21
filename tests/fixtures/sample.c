// single-line comment with "excluded_comment" and 400

#include <stdio.h>

const char *name = "Alice";
int count = 99;
float pi = 3.14;

void greet(const char *who) {
    const char *msg = "Hello";
    printf("%s\n", msg);
}

int main(void) {
    printf("world\n");
    return 0;
}
