package io.github.taobaoadclean;

import android.app.Activity;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 设置页：纯代码构建（无 XML 布局）。
 * 只负责写 RemotePreferences + 展示逐特性状态与兼容结果；不参与 hook 逻辑。
 */
public final class MainActivity extends Activity {
    private static final int BACKGROUND = Color.rgb(245, 247, 250);
    private static final int INK = Color.rgb(30, 43, 48);
    private static final int MUTED = Color.rgb(101, 116, 124);
    private static final int ACCENT = Color.rgb(255, 80, 0);
    private static final int SECTION = Color.rgb(26, 111, 160);

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, Switch> switches = new LinkedHashMap<>();
    private final Map<String, Boolean> defaults = new LinkedHashMap<>();
    private TextView status;
    private TextView host;
    private LinearLayout featureCard;
    private boolean active;
    private boolean refreshing;

    private final Runnable refreshTask = new Runnable() {
        @Override public void run() {
            if (!active) return;
            refresh();
            handler.postDelayed(this, 1000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BACKGROUND);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(16), dp(18), dp(16), dp(28));
        scroll.addView(body);
        setContentView(scroll);

        body.addView(text("淘系去广告", 25, INK, true));
        TextView subtitle = text("闲鱼 · 淘宝 · 作用域 " + Config.TARGETS.length + " 个包 · 规则 schema=" + Config.SCHEMA,
                13, MUTED, false);
        subtitle.setPadding(0, dp(4), 0, dp(14));
        body.addView(subtitle);

        LinearLayout statusCard = card();
        status = text("正在连接 LSPosed…", 14, INK, false);
        statusCard.addView(status);
        host = text("", 12, MUTED, false);
        host.setPadding(0, dp(4), 0, 0);
        statusCard.addView(host);
        body.addView(statusCard);

        section(body, "规则（每一项都标注对应页面）");
        LinearLayout toggles = card();
        toggle(toggles, Config.SPLASH, 0, "冷启动、切回前台、路由唤起三条开屏入口全拦；连遮罩和广告请求一起省掉");
        separator(toggles);
        toggle(toggles, Config.POPUP, 1, "首页浮层的所有触发源（登录成功 / 新人引导 / 主容器 idle）");
        separator(toggles);
        toggle(toggles, Config.WIDGET, 2, "首页与频道页的悬浮广告位、广告球（按资源 id 隐藏，找不到就不动）");
        separator(toggles);
        toggle(toggles, Config.SDK, 3, "关掉第三方开屏 SDK 的初始化与预加载，省电省流量");
        body.addView(toggles);

        section(body, "适配状态");
        featureCard = card();
        body.addView(featureCard);

        section(body, "生效方式");
        LinearLayout footer = card();
        Button stop = new Button(this);
        stop.setAllCaps(false);
        stop.setText("强停目标 App（让改动立即生效）");
        stop.setTextColor(ACCENT);
        stop.setBackgroundColor(Color.TRANSPARENT);
        stop.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { forceStopTargets(); }
        });
        footer.addView(stop);

        Button reset = new Button(this);
        reset.setAllCaps(false);
        reset.setText("恢复默认设置（全部开启）");
        reset.setTextColor(ACCENT);
        reset.setBackgroundColor(Color.TRANSPARENT);
        reset.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                if (App.reset()) {
                    refresh();
                    toast("已恢复默认；请强停目标 App");
                } else {
                    toast("LSPosed 服务尚未连接");
                }
            }
        });
        footer.addView(reset);
        addNote(footer, "开关写入 LSPosed 的 RemotePreferences，被 hook 的进程只读；"
                + "改完必须强停目标 App 才生效（不提供广播热更新，避免额外常驻监听）。", 12);
        body.addView(footer);
    }

    @Override protected void onResume() { super.onResume(); active = true; refreshTask.run(); }

    @Override protected void onPause() {
        active = false;
        handler.removeCallbacks(refreshTask);
        super.onPause();
    }

    private void refresh() {
        SharedPreferences prefs = App.preferences();
        if (prefs == null) {
            status.setText("● LSPosed 配置服务未连接 · 开关暂不可用");
        } else {
            status.setText("● LSPosed 配置服务已连接");
        }
        status.setTextColor(prefs == null ? MUTED : ACCENT);

        refreshing = true;
        try {
            for (Map.Entry<String, Switch> entry : switches.entrySet()) {
                Switch toggle = entry.getValue();
                toggle.setEnabled(prefs != null);
                boolean wanted = prefs == null ? defaults.get(entry.getKey())
                        : Config.readBoolean(prefs, entry.getKey(), defaults.get(entry.getKey()));
                if (toggle.isChecked() != wanted) toggle.setChecked(wanted);
            }
        } finally { refreshing = false; }

        renderFeatureStates();
    }

    /** 逐特性状态：不把「非 matched」混成一句「失败」。 */
    private void renderFeatureStates() {
        featureCard.removeAllViews();
        Bundle bundle = queryStatus();
        if (bundle == null || bundle.getString("token", "").isEmpty()) {
            addNote(featureCard, "尚未收到目标 App 的适配报告。\n强停并重新打开目标 App，再回到本页查看。", 13);
            return;
        }
        int done = bundle.getInt("done", 0);
        int total = bundle.getInt("total", 0);
        int matched = 0, partial = 0, miss = 0, off = 0;
        for (String key : Config.FEATURES) {
            String s = bundle.getString(key, "");
            if ("matched".equals(s)) matched++;
            else if ("partial".equals(s)) partial++;
            else if ("miss".equals(s)) miss++;
            else if ("off".equals(s)) off++;
        }
        host.setText("宿主 " + bundle.getString("token", "")
                + " · 已布防 " + matched + " · 部分 " + partial
                + " · 未匹配 " + miss + " · 已关闭 " + off
                + " · 进度 " + done + "/" + total);

        for (int i = 0; i < Config.FEATURES.length; i++) {
            String key = Config.FEATURES[i];
            String state = bundle.getString(key, "");
            String detail = bundle.getString(key + "_detail", "");
            String label = i < Config.FEATURE_LABELS.length ? Config.FEATURE_LABELS[i] : key;
            String page = i < Config.FEATURE_PAGES.length ? Config.FEATURE_PAGES[i] : "";
            TextView row = text(mark(state) + " " + label + "：" + describe(state), 13, INK, false);
            row.setPadding(0, dp(4), 0, 0);
            featureCard.addView(row);
            addNote(featureCard, "对应页面：" + page
                    + (detail.isEmpty() ? "" : "\n" + detail), 12);
            separator(featureCard);
        }
        addNote(featureCard, "「已布防」表示闸门已挂上；是否命中要看目标 App 日志里的 blocked 行。", 12);
    }

    private String mark(String state) {
        if ("matched".equals(state)) return "✓";
        if ("partial".equals(state)) return "◐";
        if ("miss".equals(state)) return "✕";
        if ("off".equals(state)) return "—";
        return "○";
    }

    private String describe(String state) {
        if ("matched".equals(state)) return "已布防";
        if ("partial".equals(state)) return "部分布防";
        if ("miss".equals(state)) return "未匹配";
        if ("off".equals(state)) return "已关闭";
        if ("ready".equals(state)) return "已找到，重启后生效";
        if ("scanning".equals(state)) return "正在读取代码…";
        return "待上报";
    }

    private Bundle queryStatus() {
        try {
            return getContentResolver().call(StatusProvider.URI, "get", null, null);
        } catch (Throwable ignored) { return null; }
    }

    private void forceStopTargets() {
        boolean any = false;
        for (String target : Config.TARGETS) {
            try {
                Process process = Runtime.getRuntime().exec(new String[]{"su", "-c", "am force-stop " + target});
                process.waitFor();
                any = true;
            } catch (Throwable ignored) { }
        }
        toast(any ? "已强停目标 App；重新打开即生效" : "强停失败（需要 root）；请手动在多任务里划掉目标 App");
    }

    // ── UI 小工具 ──────────────────────────────────────────────────────────

    private void toggle(LinearLayout parent, String key, int index, String detail) {
        String title = index < Config.FEATURE_LABELS.length ? Config.FEATURE_LABELS[index] : key;
        String page = index < Config.FEATURE_PAGES.length ? Config.FEATURE_PAGES[index] : "";
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setMinimumHeight(dp(72));
        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.addView(text(title, 15, INK, false));
        TextView hint = text("对应页面：" + page + "\n" + detail, 12, MUTED, false);
        hint.setPadding(0, dp(3), dp(8), 0);
        labels.addView(hint);
        row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
        Switch control = new Switch(this);
        control.setContentDescription(title);
        control.setThumbTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_checked}, new int[]{}},
                new int[]{ACCENT, Color.rgb(222, 226, 229)}));
        control.setTrackTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_checked}, new int[]{}},
                new int[]{Color.rgb(255, 205, 178), Color.rgb(190, 196, 199)}));
        control.setChecked(Config.DEFAULT_ON);
        control.setEnabled(false);
        control.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override public void onCheckedChanged(CompoundButton button, boolean checked) {
                if (refreshing || App.preferences() == null) return;
                if (!App.write(key, checked)) {
                    button.setOnCheckedChangeListener(null);
                    button.setChecked(!checked);
                    button.setOnCheckedChangeListener(this);
                    toast("保存失败");
                }
            }
        });
        row.addView(control);
        parent.addView(row);
        switches.put(key, control);
        defaults.put(key, Config.DEFAULT_ON);
    }

    private void section(LinearLayout body, String title) {
        TextView label = text(title, 14, SECTION, true);
        label.setPadding(dp(4), dp(20), 0, dp(8));
        body.addView(label);
    }

    private LinearLayout card() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(13), dp(9), dp(13), dp(9));
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(Color.WHITE);
        shape.setCornerRadius(dp(13));
        box.setBackground(shape);
        return box;
    }

    private void addNote(LinearLayout box, String message, int size) {
        TextView note = text(message, size, MUTED, false);
        note.setPadding(0, dp(4), 0, dp(5));
        box.addView(note);
    }

    private void separator(LinearLayout box) {
        View line = new View(this);
        line.setBackgroundColor(Color.rgb(239, 242, 244));
        box.addView(line, new LinearLayout.LayoutParams(-1, dp(1)));
    }

    private TextView text(String content, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(content);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(float value) { return Math.round(getResources().getDisplayMetrics().density * value); }
}
