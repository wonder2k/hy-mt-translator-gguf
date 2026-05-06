import express from "express";
import {
  buildLogisticsTranslationItems,
  translateEnToJaForLogistics,
} from "../utils/translator";

const router = express.Router();

/**
 * 单票测试接口
 */
router.post("/shipments/translate-demo", async (req, res, next) => {
  try {
    const {
      receiverAddressEn,
      itemNameEn,
      receiverNameEn,
      memoEn,
    } = req.body;

    const items = buildLogisticsTranslationItems({
      receiverAddressEn,
      itemNameEn,
      receiverNameEn,
      memoEn,
    });

    const [receiverAddressJa, itemNameJa, receiverNameJa, memoJa] =
      await translateEnToJaForLogistics(items);

    res.json({
      success: true,
      data: {
        receiverAddressEn,
        receiverAddressJa,
        itemNameEn,
        itemNameJa,
        receiverNameEn,
        receiverNameJa,
        memoEn,
        memoJa,
      },
    });
  } catch (error) {
    next(error);
  }
});

/**
 * 多票批量翻译接口
 */
router.post("/shipments/batch-translate", async (req, res, next) => {
  try {
    const shipments = Array.isArray(req.body?.shipments) ? req.body.shipments : [];

    if (!shipments.length) {
      return res.status(400).json({
        success: false,
        message: "shipments must be a non-empty array",
      });
    }

    const flatItems = shipments.flatMap((shipment: any) =>
      buildLogisticsTranslationItems({
        receiverAddressEn: shipment.receiverAddressEn,
        itemNameEn: shipment.itemNameEn,
        receiverNameEn: shipment.receiverNameEn,
        memoEn: shipment.memoEn,
      }),
    );

    const translated = await translateEnToJaForLogistics(flatItems);

    const result = shipments.map((shipment: any, index: number) => {
      const offset = index * 4;
      return {
        ...shipment,
        receiverAddressJa: translated[offset],
        itemNameJa: translated[offset + 1],
        receiverNameJa: translated[offset + 2],
        memoJa: translated[offset + 3],
      };
    });

    return res.json({
      success: true,
      count: result.length,
      data: result,
    });
  } catch (error) {
    next(error);
  }
});

export default router;
