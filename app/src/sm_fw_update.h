/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef SM_FW_UPDATE_H
#define SM_FW_UPDATE_H

/** @file sm_fw_update.h
 *
 * @brief Firmware update functionality shared by the DFU and FOTA features.
 * @{
 */

/**
 * @brief Check the result of a firmware update after boot.
 *
 * Confirms an application image that MCUboot has swapped in, and reports the result of an
 * application FOTA. The result of a modem update is handled separately by the modem
 * library DFU result hook.
 */
void sm_fw_update_boot_check(void);

/** @} */

#endif /* SM_FW_UPDATE_H */
