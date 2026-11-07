/**
 * Global Market Desk — shortcode (Code Snippets मध्ये paste करा, "<?php" ओळ नको)
 *
 * वापर (Elementor → Shortcode widget):
 *   Public पान:  [gmd_dashboard]
 *   Private पान: [gmd_dashboard mode="private"]
 *
 * CSS/JS GitHub Pages वरून येतात — त्यामुळे पुढच्या सुधारणा WP मध्ये paste कराव्या लागत नाहीत.
 * S2: "What moved" वाक्यं server-side HTML मध्येही येतात (Google ला दिसतात); JS नंतर तोच भाग नव्याने दाखवतो.
 * S4 (SEO): public dashboard पानावर meta description रोजच्या "What moved" वरून + JSON-LD structured data.
 *           Yoast / Rank Math असल्यास त्यांच्याच description मध्ये भरतो (duplicate meta नाही).
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

// हे पान public dashboard आहे का (shortcode आहे, private mode नाही)
function gmd_is_public_dashboard(): bool {
    if (!is_singular()) {
        return false;
    }
    $content = (string) get_post_field('post_content', get_queried_object_id());
    return false !== strpos($content, '[gmd_dashboard') && false === strpos($content, 'mode="private"');
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
            add_action('wp_head', function () use ($desc) {
                echo '<meta name="description" content="' . esc_attr($desc) . '">' . "\n";
            }, 1);
        }
    }
    // Structured data: Google ला पान कशाबद्दल आहे आणि कधी update झालं ते सांगते
    add_action('wp_head', function () use ($desc) {
        $meta = gmd_market_meta();
        $ld   = array(
            '@context'    => 'https://schema.org',
            '@type'       => 'WebPage',
            'name'        => wp_get_document_title(),
            'url'         => get_permalink(),
            'description' => '' !== $desc ? $desc : 'Delayed global and Indian market data for information.',
            'inLanguage'  => 'en-IN',
            'publisher'   => array('@type' => 'Organization', 'name' => 'Sahare Wealth', 'url' => home_url('/')),
        );
        if (!empty($meta['updated'])) {
            $ld['dateModified'] = $meta['updated'];
        }
        echo '<script type="application/ld+json">' . wp_json_encode($ld) . '</script>' . "\n";
    }, 20);
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
