/**
 * Global Market Desk — shortcode (Code Snippets मध्ये paste करा, "<?php" ओळ नको)
 *
 * वापर (Elementor → Shortcode widget):
 *   Public पान:  [gmd_dashboard]
 *   Private पान: [gmd_dashboard mode="private"]
 *
 * CSS/JS GitHub Pages वरून येतात — त्यामुळे पुढच्या सुधारणा WP मध्ये paste कराव्या लागत नाहीत.
 */
if (!defined('ABSPATH')) {
    exit; // थेट file उघडल्यास थांबवा
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

    return '<div class="gmd" id="gmd-root" data-mode="' . esc_attr($mode) . '"></div>';
});
