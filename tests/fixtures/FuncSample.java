/**
 * Javadoc with "excluded_doc" value.
 */
public class FuncSample {
    // class-level field - excluded with functions-only
    String classField = "class_field";
    int classNum = 55;

    public String myMethod() {
        String x = "method_string";
        int n = 77;
        return x;
    }

    private void anotherMethod(String param) {
        System.out.println("another_method");
    }
}
