/**
 * Global Market Desk — shortcode (Code Snippets मध्ये paste करा, "<?php" ओळ नको)
 *
 * वापर (Elementor → Shortcode widget):
 *   Public पान:  [gmd_dashboard]
 *   Private पान: [gmd_dashboard mode="private"]
 *
 * CSS/JS GitHub Pages वरून येतात — त्यामुळे पुढच्या सुधारणा WP मध्ये paste कराव्या लागत नाहीत.
 * S2: "What moved" वाक्यं server-side HTML मध्येही येतात (Google ला दिसतात); JS नंतर तोच भाग नव्याने दाखवतो.
 */
if (!defined('ABSPATH')) {
    exit; // थेट file उघडल्यास थांबवा
}

// market.json मधून summary वाक्यं — 15 मिनिटं cache (fail झाल्यास 2 मिनिटं)
function gmd_summary_lines(): array {
    $cache_key = 'gmd_summary_v1';
    $cached    = get_transient($cache_key);
    if (false !== $cached) {
        return (array) $cached;
    }

    $lines = array();
    $res   = wp_remote_get('https://pankajsahare.github.io/global-market-desk/data/market.json', array('timeout' => 8));
    if (!is_wp_error($res) && 200 === (int) wp_remote_retrieve_response_code($res)) {
        $data = json_decode(wp_remote_retrieve_body($res), true);
        if (is_array($data) && !empty($data['summary']) && is_array($data['summary'])) {
            $lines = array_slice(array_map('strval', $data['summary']), 0, 6);
        }
    }
    set_transient($cache_key, $lines, empty($lines) ? 2 * MINUTE_IN_SECONDS : 15 * MINUTE_IN_SECONDS);
    return $lines;
}

add_shortcode('gmd_dashboard', function ($atts) {
    $atts = shortcode_atts(array('mode' => 'public'), $atts, 'gmd_dashboard');
    $mode = ('private' === $atts['mode']) ? 'private' : 'public';

    // Private mode: पान चुकून public झालं तरी फक्त login असलेल्या editors/admins नाच दिसेल
    if ('private' === $mode && !current_user_can('edit_pages')) {
        return '';
    }

    $base = 'https://pankajsahare.github.io/global-market-desk/widget/';
    // version null → WP "?ver=" जोडत नाही; GitHub Pages चा 10 मिनिटांचा cache पुरेसा
    wp_enqueue_style('gmd-widget', $base . 'gmd.css', array(), null);
    wp_enqueue_script('gmd-widget', $base . 'gmd.js', array(), null, true);

    // JS load होईपर्यंत (आणि search engines साठी) साधं HTML; JS हा भाग बदलून पूर्ण dashboard दाखवतो
    $inner = '';
    $lines = gmd_summary_lines();
    if (!empty($lines)) {
        $inner .= '<h2>Global Markets — What Moved</h2><ul>';
        foreach ($lines as $line) {
            $inner .= '<li>' . esc_html($line) . '</li>';
        }
        $inner .= '</ul><p><small>Market data is delayed and shown for information only; not investment advice.</small></p>';
    }

    return '<div class="gmd" id="gmd-root" data-mode="' . esc_attr($mode) . '">' . $inner . '</div>';
});
