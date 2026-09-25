import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

public class DumpZapHistory {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Usage: DumpZapHistory <db-path-without-extension>");
        }
        Class.forName("org.hsqldb.jdbc.JDBCDriver");
        try (Connection connection = DriverManager.getConnection("jdbc:hsqldb:file:" + args[0] + ";ifexists=true", "SA", "")) {
            String sql = "SELECT HISTORYID, METHOD, URI, REQHEADER, REQBODY, RESHEADER, RESBODY "
                    + "FROM HISTORY WHERE URI LIKE ? ORDER BY HISTORYID";
            try (PreparedStatement statement = connection.prepareStatement(sql)) {
                statement.setString(1, "%moapbe.spp-distribucia.sk%");
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
        return value.replaceAll("Bearer [A-Za-z0-9._~+\\\\/-]+\\|[A-Za-z0-9._~+\\\\/-]+", "Bearer <redacted>");
    }
}
