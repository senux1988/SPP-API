import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.regex.Pattern;

public class DumpZapHistory {
    private static final Pattern SENSITIVE_HEADER = Pattern.compile(
            "(?im)^(authorization|cookie|set-cookie):\\s*.*$");
    private static final Pattern SENSITIVE_JSON = Pattern.compile(
            "(?i)(\\\"(?:username|email|password|access_token|refresh_token|id_token|token|fcm_token|code)\\\"\\s*:\\s*\\\")[^\\\"]*(\\\")");
    private static final Pattern SENSITIVE_FORM = Pattern.compile(
            "(?i)((?:^|&)(?:username|email|password|access_token|refresh_token|id_token|token|code)=)[^&\\s]*");
    private static final Pattern SENSITIVE_QUERY = Pattern.compile(
            "(?i)([?&](?:code|access_token|refresh_token|id_token|token)=)[^&\\s]*");

    public static void main(String[] args) throws Exception {
        if (args.length < 1 || args.length > 2) {
            throw new IllegalArgumentException(
                    "Usage: DumpZapHistory <db-path-without-extension> [URI LIKE pattern]");
        }
        String uriPattern = args.length == 2 ? args[1] : "%";
        Class.forName("org.hsqldb.jdbc.JDBCDriver");
        try (Connection connection = DriverManager.getConnection("jdbc:hsqldb:file:" + args[0] + ";ifexists=true", "SA", "")) {
            String sql = "SELECT HISTORYID, METHOD, URI, REQHEADER, REQBODY, RESHEADER, RESBODY "
                    + "FROM HISTORY WHERE URI LIKE ? ORDER BY HISTORYID";
            try (PreparedStatement statement = connection.prepareStatement(sql)) {
                statement.setString(1, uriPattern);
                try (ResultSet rows = statement.executeQuery()) {
                    while (rows.next()) {
                        System.out.println("==== " + rows.getInt("HISTORYID") + " "
                                + rows.getString("METHOD") + " " + rows.getString("URI"));
                        System.out.println("-- request headers");
                        System.out.println(redact(rows.getString("REQHEADER")));
                        printBody("-- request body", rows.getBytes("REQBODY"));
                        System.out.println("-- response headers");
                        System.out.println(rows.getString("RESHEADER"));
                        printBody("-- response body", rows.getBytes("RESBODY"));
                    }
                }
            }
        }
    }

    private static void printBody(String title, byte[] body) {
        System.out.println(title);
        if (body == null || body.length == 0) {
            return;
        }
        System.out.println(redact(new String(body, StandardCharsets.UTF_8)));
    }

    private static String redact(String value) {
        if (value == null) {
            return "";
        }
        String redacted = SENSITIVE_HEADER.matcher(value).replaceAll("$1: <redacted>");
        redacted = SENSITIVE_JSON.matcher(redacted).replaceAll("$1<redacted>$2");
        redacted = SENSITIVE_FORM.matcher(redacted).replaceAll("$1<redacted>");
        return SENSITIVE_QUERY.matcher(redacted).replaceAll("$1<redacted>");
    }
}
