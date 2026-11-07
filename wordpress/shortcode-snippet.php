/**
 * Global Market Desk — shortcode (Code Snippets मध्ये paste करा, "<?php" ओळ नको)
 *
 * वापर (Elementor → Shortcode widget):
 *   Public पान:  [gmd_dashboard]
 *   Private पान: [gmd_dashboard mode="private"]
 *
 * CSS/JS GitHub Pages वरून येतात — त्यामुळे पुढच्या सुधारणा WP मध्ये paste कराव्या लागत नाहीत.
 * S2: "What moved" वाक्यं server-side HTML मध्येही येतात (Google ला दिसतात); JS नंतर तोच भाग नव्याने दाखवतो.
 * S4 (SEO): public dashboard पानावर meta description आणि link preview (og/twitter) रोजच्या "What moved" वरून.
 *           Structured data ThinkRank देतो — दुसरा WebPage schema इथे मुद्दाम नाही.
 *           Yoast / Rank Math असल्यास त्यांच्याच description मध्ये भरतो; इतर (उदा. ThinkRank, WPCode)
 *           असल्यास त्यांचं description बदलतो — पानावर नेहमी एकच description.
 */
if (!defined('ABSPATH')) {
    exit; // थेट file उघडल्यास थांबवा
}

// market.json मधून summary वाक्यं + updated वेळ — 15 मिनिटं cache (fail झाल्यास 2 मिनिटं)
function gmd_market_meta(): array {
    $cache_key = 'gmd_meta_v2';
    $cached    = get_transient($cache_key);
    if (false !== $cached) {
        return (array) $cached;
    }

    $meta = array('lines' => array(), 'updated' => '');
    $res  = wp_remote_get('https://pankajsahare.github.io/global-market-desk/data/market.json', array('timeout' => 8));
    if (!is_wp_error($res) && 200 === (int) wp_remote_retrieve_response_code($res)) {
        $data = json_decode(wp_remote_retrieve_body($res), true);
        if (is_array($data) && !empty($data['summary']) && is_array($data['summary'])) {
            $meta['lines']   = array_slice(array_map('strval', $data['summary']), 0, 6);
            $meta['updated'] = isset($data['updated']) ? (string) $data['updated'] : '';
        }
    }
    set_transient($cache_key, $meta, empty($meta['lines']) ? 2 * MINUTE_IN_SECONDS : 15 * MINUTE_IN_SECONDS);
    return $meta;
}

function gmd_summary_lines(): array {
    return gmd_market_meta()['lines'];
}

// TODO [मॅन्युअल बदल]: public dashboard पानाचा slug | उदा.: 'global-market' (URL मधला शेवटचा भाग)
//   न बदलल्यास: पान shortcode वरून शोधलं जातं (Elementor data सकट)
const GMD_PUBLIC_SLUG = 'global-market';  // ← येथे बदला

// हे पान public dashboard आहे का (slug जुळतो, किंवा shortcode आहे आणि private mode नाही)
function gmd_is_public_dashboard(): bool {
    if (!is_singular()) {
        return false;
    }
    if (GMD_PUBLIC_SLUG !== '' && is_page(GMD_PUBLIC_SLUG)) {
        return true;
    }
    $id = get_queried_object_id();
    // Elementor shortcode post_content मध्ये नव्हे तर _elementor_data मध्ये ठेवतो — दोन्ही तपासा
    $haystack = (string) get_post_field('post_content', $id) . ' ' . (string) get_post_meta($id, '_elementor_data', true);
    if (false === strpos($haystack, 'gmd_dashboard')) {
        return false;
    }
    return !preg_match('/gmd_dashboard[^\]]*private/i', $haystack);
}

// Google साठी ~155 अक्षरांचं description (शब्द न तोडता)
function gmd_meta_description(): string {
    $lines = gmd_summary_lines();
    if (empty($lines)) {
        return '';
    }
    $text = 'Global markets today: ' . implode(' ', array_slice($lines, 0, 2));
    if (strlen($text) > 155) {
        $text = rtrim(substr($text, 0, 152));
        $text = substr($text, 0, (int) strrpos($text, ' ')) . '...';
    }
    return $text;
}

// HTML मधले सगळे <meta name="description"> काढून पहिल्याच्या जागी आमचा एक ठेवा (नसल्यास </head> आधी)
function gmd_replace_meta_description(string $html, string $desc): string {
    $tag     = '<meta name="description" content="' . esc_attr($desc) . '">';
    $pattern = '/<meta\b[^>]*\bname\s*=\s*["\']description["\'][^>]*>\s*/i';
    $seen    = 0;
    $html    = preg_replace_callback($pattern, function () use (&$seen, $tag) {
        return 0 === $seen++ ? $tag . "\n" : '';
    }, $html);
    if (0 === $seen) {
        $html = preg_replace('/<\/head>/i', $tag . "\n</head>", $html, 1);
    }
    // WhatsApp / Facebook / X link preview मध्येही आजचा मजकूर
    $safe = esc_attr($desc);
    $html = preg_replace('/(<meta\b[^>]*\bproperty\s*=\s*["\']og:description["\'][^>]*\bcontent\s*=\s*["\'])[^"\']*/i', '${1}' . $safe, $html);
    $html = preg_replace('/(<meta\b[^>]*\bname\s*=\s*["\']twitter:description["\'][^>]*\bcontent\s*=\s*["\'])[^"\']*/i', '${1}' . $safe, $html);
    return $html;
}

add_action('template_redirect', function () {
    if (!gmd_is_public_dashboard()) {
        return;
    }
    $desc = gmd_meta_description();
    if ('' !== $desc) {
        if (defined('WPSEO_VERSION')) {
            add_filter('wpseo_metadesc', function () use ($desc) { return $desc; });
        } elseif (class_exists('RankMath')) {
            add_filter('rank_math/frontend/description', function () use ($desc) { return $desc; });
        } else {
            // इतर SEO plugin (उदा. ThinkRank) किंवा WPCode चं description असेल तर ते बदला; नसेल तर जोडा.
            // पानावर नेहमी एकच description राहतो.
            ob_start(function ($html) use ($desc) {
                return gmd_replace_meta_description((string) $html, $desc);
            });
        }
    }
});

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
